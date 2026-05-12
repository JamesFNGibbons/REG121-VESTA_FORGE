"""Dense (OpenAI) and sparse (FastEmbed SPLADE) embeddings."""

from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

_DENSE_MODEL = "text-embedding-3-small"
_DENSE_DIM = 1536

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


def embed_dense(*, openai_api_key: str, text: str) -> list[float]:
    client = OpenAI(api_key=openai_api_key)
    resp = client.embeddings.create(model=_DENSE_MODEL, input=text)
    vec = resp.data[0].embedding
    if len(vec) != _DENSE_DIM:
        raise ValueError(f"Expected {_DENSE_DIM} dims, got {len(vec)}")
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


def embed_hybrid(*, openai_api_key: str, text: str) -> tuple[list[float], list[int], list[float]]:
    dense = embed_dense(openai_api_key=openai_api_key, text=text)
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
    parts: list[str] = [
        str(catalogue.get("name", "")),
        f"category {catalogue.get('category', '')}",
        f"variant {catalogue.get('variant_name', '')}",
        f"vibe {'; '.join(e.get('vibe') or [])}",
        f"anti_vibe {'; '.join(e.get('anti_vibe') or [])}",
        f"aesthetic_movement {e.get('aesthetic_movement', '')}",
        f"design_era {e.get('design_era', '')}",
        f"trust {er.get('trust', '')} excitement {er.get('excitement', '')} "
        f"warmth {er.get('warmth', '')} authority {er.get('authority', '')}",
        f"first_impression {e.get('first_impression', '')}",
        f"conversion_role {e.get('conversion_role', '')}",
        f"industry_perfect {'; '.join(e.get('industry_perfect') or [])}",
        f"industry_avoid {'; '.join(e.get('industry_avoid') or [])}",
        f"price_point_signal {e.get('price_point_signal', '')}",
        f"layout_pattern {e.get('layout_pattern', '')}",
        f"narrative_role {e.get('narrative_role', '')}",
        str(catalogue.get("description", "")),
        UK_SMB_TAIL,
    ]
    return " ".join(p for p in parts if p and p != "None")
