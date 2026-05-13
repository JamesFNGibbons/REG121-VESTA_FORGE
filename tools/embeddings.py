"""Dense embeddings via LiteLLM (OpenAI-compatible /v1/embeddings) + sparse (FastEmbed SPLADE) locally."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from tools.litellm_client import openai_client_for_litellm

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
    client = openai_client_for_litellm(base_url, api_key)
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
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
        embedding_model=settings.litellm_embedding_model,
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
    """Hybrid retrieval string: prefer LLM enrichment; catalogue only as fallback when enrichment is absent."""
    e = enrichment or {}
    display = (e.get("llm_display_name") or "").strip()
    impression = (e.get("first_impression") or "").strip()
    tags = e.get("search_tags") or []
    aesthetic = (e.get("aesthetic_movement") or "").strip()
    category = str(catalogue.get("category") or "").strip()

    has_enrichment = bool(display or impression or tags or aesthetic)

    if has_enrichment:
        tag_str = " ".join(str(t).strip() for t in tags if str(t).strip())
        parts = [display, category, aesthetic, tag_str, impression]
        return " ".join(p for p in parts if p)

    # Fallback when inspect failed or returned nothing useful
    name = str(catalogue.get("name") or "").strip()
    desc = str(catalogue.get("description") or "").strip()
    parts = [name, f"category {category}", desc, UK_SMB_TAIL]
    return " ".join(p for p in parts if p and p != "None")
