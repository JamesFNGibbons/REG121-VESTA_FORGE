"""Dense embeddings via DeepInfra (OpenAI-compatible) + sparse (FastEmbed SPLADE) locally."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from tools.openai_compat import openai_client_at_base_url

if TYPE_CHECKING:
    from tools.settings import Settings

logger = logging.getLogger(__name__)

_splade_model: Any = None


def _splade() -> Any:
    global _splade_model
    if _splade_model is None:
        from fastembed import SparseTextEmbedding

        _splade_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")
        logger.info("Loaded FastEmbed SPLADE model")
    return _splade_model


def warm_splade_model() -> None:
    """Eagerly load SPLADE (used by Docker build warmup)."""
    _splade()


def embed_dense(
    *,
    base_url: str,
    api_key: str,
    embedding_model: str,
    expected_dim: int,
    text: str,
) -> list[float]:
    client = openai_client_at_base_url(base_url, api_key)
    resp = client.embeddings.create(model=embedding_model, input=text)
    vec = resp.data[0].embedding
    if len(vec) != expected_dim:
        raise ValueError(f"Expected {expected_dim} dims (set DENSE_VECTOR_SIZE to match), got {len(vec)}")
    return list(vec)


def embed_sparse(text: str) -> tuple[list[int], list[float]]:
    model = _splade()
    gen = model.embed([text])
    emb = next(gen)
    ind = emb.indices
    val = emb.values
    if hasattr(ind, "tolist"):
        ind = ind.tolist()
    if hasattr(val, "tolist"):
        val = val.tolist()
    indices = [int(i) for i in ind]
    values = [float(v) for v in val]
    if not indices:
        return [0], [0.0]
    return indices, values


def embed_hybrid(*, settings: "Settings", text: str) -> tuple[list[float], list[int], list[float]]:
    dense = embed_dense(
        base_url=settings.deepinfra_base_url,
        api_key=settings.deepinfra_api_key,
        embedding_model=settings.deepinfra_embedding_model,
        expected_dim=settings.dense_vector_size,
        text=text,
    )
    sparse_i, sparse_v = embed_sparse(text)
    return dense, sparse_i, sparse_v


UK_SMB_TAIL = (
    "Nottingham Sheffield Leeds Manchester Birmingham London Bristol Edinburgh Cardiff "
    "UK small business SMB"
)


def build_embedding_text(
    *,
    catalogue: dict[str, Any],
    enrichment: dict[str, Any] | None,
) -> str:
    """Rich paragraph for hybrid retrieval (dense + SPLADE)."""
    e = enrichment or {}
    er = e.get("emotional_response") or {}
    display = (e.get("llm_display_name") or "").strip() or str(catalogue.get("name") or "")
    blurb = (e.get("best_for") or "").strip() or str(catalogue.get("description") or "")
    parts: list[str] = [
        display,
        f"category {catalogue.get('category', '')}",
        f"variant {catalogue.get('variant_name', '')}",
        f"search_tags {'; '.join(e.get('search_tags') or [])}",
        f"llm_mood {e.get('llm_mood', '')}",
        f"vibe {'; '.join(e.get('vibe') or [])}",
        f"anti_vibe {'; '.join(e.get('anti_vibe') or [])}",
        f"aesthetic_movement {e.get('aesthetic_movement', '')}",
        f"design_era {e.get('design_era', '')}",
        f"trust {er.get('trust', '')} excitement {er.get('excitement', '')} "
        f"warmth {er.get('warmth', '')} authority {er.get('authority', '')} "
        f"safety {er.get('safety', '')} aspiration {er.get('aspiration', '')} urgency {er.get('urgency', '')}",
        f"first_impression {e.get('first_impression', '')}",
        f"conversion_role {e.get('conversion_role', '')}",
        f"buyer_journey_stage {e.get('buyer_journey_stage', '')}",
        f"content_density {e.get('content_density', '')}",
        f"industry_perfect {'; '.join(e.get('industry_perfect') or [])}",
        f"industry_good {'; '.join(e.get('industry_good') or [])}",
        f"industry_avoid {'; '.join(e.get('industry_avoid') or [])}",
        f"price_point_signal {e.get('price_point_signal', '')}",
        f"layout_pattern {e.get('layout_pattern', '')}",
        f"narrative_role {e.get('narrative_role', '')}",
        blurb,
        UK_SMB_TAIL,
    ]
    return " ".join(p for p in parts if p and p != "None")
