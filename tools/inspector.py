"""Qwen metadata enrichment via LiteLLM (OpenAI-compatible streaming chat)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol, runtime_checkable

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError, field_validator
from tenacity import Retrying, stop_after_attempt, wait_exponential

from tools.litellm_client import openai_client_for_litellm

logger = logging.getLogger(__name__)

HTML_MAX_FOR_LLM = 4000

# Strip common model "thinking" wrappers before JSON.parse
_THINK_BLOCK_RES = [
    re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE),
    re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE),
    re.compile(r"<redacted_reasoning>[\s\S]*?</redacted_reasoning>", re.IGNORECASE),
    re.compile(r"<reasoning>[\s\S]*?</reasoning>", re.IGNORECASE),
]


@runtime_checkable
class StreamingSink(Protocol):
    """Live UI: think/reasoning vs answer tokens (JSON path)."""

    def on_think(self, fragment: str) -> None: ...

    def on_answer(self, fragment: str) -> None: ...

    def refresh(self) -> None: ...


class JsDependency(BaseModel):
    name: str = ""
    version: str = ""
    cdn_url: str = ""
    load_position: str = "body-end"
    required: bool = True


class JavascriptBlock(BaseModel):
    requires_js: bool = False
    js_type: str = "none"
    js_complexity: str = "none"
    js_purpose: list[str] = Field(default_factory=list)
    graceful_without_js: bool = True
    dependencies: list[JsDependency] = Field(default_factory=list)
    inline_js_present: bool = False


class EmotionalResponse(BaseModel):
    trust: int = Field(default=5, ge=1, le=10)
    excitement: int = Field(default=5, ge=1, le=10)
    warmth: int = Field(default=5, ge=1, le=10)
    authority: int = Field(default=5, ge=1, le=10)
    safety: int = Field(default=5, ge=1, le=10)
    curiosity: int = Field(default=5, ge=1, le=10)
    aspiration: int = Field(default=5, ge=1, le=10)
    urgency: int = Field(default=5, ge=1, le=10)


class InspectionResult(BaseModel):
    vibe: list[str] = Field(default_factory=list)
    anti_vibe: list[str] = Field(default_factory=list)
    design_era: str = "timeless"
    aesthetic_movement: str = "corporate-minimal"
    emotional_response: EmotionalResponse = Field(default_factory=EmotionalResponse)
    first_impression: str = ""
    psychological_triggers: list[str] = Field(default_factory=list)
    conversion_role: str = "trust-builder"
    cta_prominence: str = "moderate"
    buyer_journey_stage: str = "awareness"
    industry_perfect: list[str] = Field(default_factory=list)
    industry_good: list[str] = Field(default_factory=list)
    industry_avoid: list[str] = Field(default_factory=list)
    price_point_signal: str = "mid"
    layout_pattern: str = "centered"
    content_density: str = "balanced"
    white_space: str = "moderate"
    visual_hierarchy: str = "moderate"
    page_position: list[str] = Field(default_factory=lambda: ["any"])
    narrative_role: str = "hook-and-establish"
    javascript: JavascriptBlock = Field(default_factory=JavascriptBlock)
    requires_image: bool = False
    image_type: str = "none"
    mobile_behaviour: str = "stacks-vertically"
    wcag_level: str = "AA"
    performance_impact: str = "minimal"
    complexity: int = Field(default=5, ge=1, le=10)
    best_for: str = ""

    @field_validator(
        "design_era",
        "aesthetic_movement",
        "conversion_role",
        "cta_prominence",
        "buyer_journey_stage",
        "price_point_signal",
        "layout_pattern",
        "content_density",
        "white_space",
        "visual_hierarchy",
        "narrative_role",
        "image_type",
        "mobile_behaviour",
        "wcag_level",
        "performance_impact",
        mode="before",
    )
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


def strip_thinking_blocks(text: str) -> str:
    """Remove model thinking / scratch XML so JSON can be parsed."""
    t = text
    for rx in _THINK_BLOCK_RES:
        t = rx.sub("", t)
    return t.strip()


def _parse_inspection_json(raw: str) -> InspectionResult:
    cleaned = _strip_json_fence(strip_thinking_blocks(raw))
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Model returned non-JSON; raw prefix: %s", cleaned[:200])
        raise
    try:
        return InspectionResult.model_validate(data)
    except ValidationError as exc:
        logger.warning("Inspection JSON failed validation: %s", exc)
        raise


_SYSTEM_PROMPT = (
    "You are a meticulous UK-focused web design analyst. "
    "Output only a single JSON object with no markdown fences and no commentary outside that object. "
    "The JSON must match the requested schema keys exactly."
)


def _user_prompt(*, catalogue: dict[str, Any], html_truncated: str) -> str:
    meta = json.dumps(
        {
            "component_name": catalogue.get("name"),
            "category": catalogue.get("category"),
            "description": catalogue.get("description"),
            "mood": catalogue.get("mood"),
            "business_types": catalogue.get("business_types"),
            "visual_tags": catalogue.get("visual_tags"),
        },
        ensure_ascii=False,
    )
    schema_hint = """
Required JSON keys and types:
- vibe: string array (aesthetic descriptors)
- anti_vibe: string array
- design_era: one of timeless, modern-2024, brutalist, classic
- aesthetic_movement: string (e.g. corporate-minimal, warm-editorial)
- emotional_response: object with trust, excitement, warmth, authority, safety, curiosity, aspiration, urgency (integers 1-10)
- first_impression: string (one sentence)
- psychological_triggers: string array
- conversion_role: string (e.g. trust-builder, direct-converter)
- cta_prominence: one of none, subtle, moderate, strong, dominant
- buyer_journey_stage: one of awareness, consideration, decision, retention
- industry_perfect: string array (specific UK business types)
- industry_good: string array
- industry_avoid: string array
- price_point_signal: one of budget, mid, premium-mid, premium, luxury
- layout_pattern: string (e.g. split-left, centered, full-bleed, grid)
- content_density: one of minimal, balanced, rich, dense
- white_space: one of tight, moderate, generous, extreme
- visual_hierarchy: one of weak, moderate, strong
- page_position: string array (values from first, second, middle, last, any)
- narrative_role: string
- javascript: object with requires_js (bool), js_type (none|alpine|vanilla|library),
  js_complexity (none|minimal|moderate|complex), js_purpose (string array),
  graceful_without_js (bool), dependencies (array of {name, version, cdn_url, load_position, required}),
  inline_js_present (bool)
- requires_image: bool
- image_type: string
- mobile_behaviour: string
- wcag_level: string (prefer AA)
- performance_impact: one of minimal, moderate, heavy
- complexity: integer 1-10
- best_for: string (one precise sentence for UK SMB context)
"""
    return f"Catalogue context (JSON):\n{meta}\n\nHTML (truncated):\n{html_truncated}\n{schema_hint}"


def _delta_reasoning(delta: Any) -> str | None:
    for attr in ("reasoning_content", "reasoning", "thinking"):
        v = getattr(delta, attr, None)
        if isinstance(v, str) and v:
            return v
    return None


def _stream_chat_to_text(
    *,
    client: OpenAI,
    model: str,
    catalogue: dict[str, Any],
    html_truncated: str,
    stream_sink: StreamingSink | None,
) -> str:
    stream = client.chat.completions.create(
        model=model,
        temperature=0.2,
        stream=True,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(catalogue=catalogue, html_truncated=html_truncated)},
        ],
        extra_body={"thinking": {"type": "disabled"}},
    )
    parts: list[str] = []
    for chunk in stream:
        if not chunk.choices:
            continue
        ch0 = chunk.choices[0]
        delta = ch0.delta
        if delta is None:
            continue
        rc = _delta_reasoning(delta)
        if rc and stream_sink is not None:
            stream_sink.on_think(rc)
            stream_sink.refresh()
        c = getattr(delta, "content", None) or ""
        if c:
            parts.append(c)
            if stream_sink is not None:
                stream_sink.on_answer(c)
                stream_sink.refresh()
    return "".join(parts)


def inspect_component(
    *,
    base_url: str,
    api_key: str,
    model: str,
    catalogue: dict[str, Any],
    html: str,
    max_retries: int,
    stream_sink: StreamingSink | None = None,
) -> InspectionResult:
    truncated = html[:HTML_MAX_FOR_LLM]
    client = openai_client_for_litellm(base_url, api_key)

    def _call() -> InspectionResult:
        raw = _stream_chat_to_text(
            client=client,
            model=model,
            catalogue=catalogue,
            html_truncated=truncated,
            stream_sink=stream_sink,
        )
        return _parse_inspection_json(raw)

    retrying = Retrying(
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        stop=stop_after_attempt(max(1, max_retries)),
        reraise=True,
    )

    try:
        return retrying(_call)
    except Exception as exc:
        logger.exception("Inspection failed after retries: %s", exc)
        raise


def index_fields_from_inspection(result: InspectionResult) -> dict[str, Any]:
    """Top-level payload fields used for Qdrant payload indexes and filtering."""
    er = result.emotional_response
    return {
        "emotional_trust": float(er.trust),
        "emotional_authority": float(er.authority),
        "emotional_warmth": float(er.warmth),
        "js_type": result.javascript.js_type,
        "js_complexity": result.javascript.js_complexity,
        "price_point_signal": result.price_point_signal,
        "conversion_role": result.conversion_role,
        "layout_pattern": result.layout_pattern,
        "js_dependencies": [dep.model_dump() for dep in result.javascript.dependencies],
    }


def inspection_to_payload_dict(result: InspectionResult) -> dict[str, Any]:
    """Backward-compatible name: full enrichment dict + index helpers."""
    return {**result.model_dump(), **index_fields_from_inspection(result)}
