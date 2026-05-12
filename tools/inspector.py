"""Qwen metadata enrichment via LiteLLM (OpenAI-compatible chat completions)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError, field_validator
from tenacity import Retrying, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

HTML_MAX_FOR_LLM = 4000


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


def _litellm_openai_client(base_url: str, api_key: str) -> OpenAI:
    root = base_url.rstrip("/")
    if not root.endswith("/v1"):
        root = root + "/v1"
    return OpenAI(base_url=root, api_key=api_key or "dummy")


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


def _parse_inspection_json(raw: str) -> InspectionResult:
    cleaned = _strip_json_fence(raw)
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
    "Return JSON only with no markdown fences and no commentary. "
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


def inspect_component(
    *,
    base_url: str,
    api_key: str,
    model: str,
    catalogue: dict[str, Any],
    html: str,
    max_retries: int,
) -> InspectionResult:
    truncated = html[:HTML_MAX_FOR_LLM]
    client = _litellm_openai_client(base_url, api_key)

    def _call() -> InspectionResult:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(catalogue=catalogue, html_truncated=truncated)},
            ],
        )
        content = resp.choices[0].message.content or ""
        return _parse_inspection_json(content)

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
