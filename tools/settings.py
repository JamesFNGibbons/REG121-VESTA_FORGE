"""Typed environment settings for the ingestion CLI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection_name: str
    litellm_base_url: str
    litellm_api_key: str
    litellm_inspector_model: str
    deepinfra_base_url: str
    deepinfra_api_key: str
    deepinfra_embedding_model: str
    dense_vector_size: int
    forge_default_handler: str
    ingest_batch_size: int
    ingest_max_retries: int
    component_library_root: Path


def _settings_for(lib: Path) -> Settings:
    return Settings(
        qdrant_url=os.getenv("QDRANT_URL", "").strip(),
        qdrant_api_key=os.getenv("QDRANT_API_KEY", "").strip(),
        qdrant_collection_name=os.getenv("QDRANT_COLLECTION_NAME", "reg121_design_brain").strip(),
        litellm_base_url=os.getenv("LITELLM_BASE_URL", "https://litellm.ai.reg121.com").strip().rstrip("/"),
        litellm_api_key=os.getenv("LITELLM_API_KEY", "").strip(),
        litellm_inspector_model=os.getenv("LITELLM_INSPECTOR_MODEL", "qwen3-32b").strip(),
        deepinfra_base_url=os.getenv(
            "DEEPINFRA_BASE_URL", "https://api.deepinfra.com/v1/openai"
        ).strip().rstrip("/"),
        deepinfra_api_key=os.getenv("DEEPINFRA_API_KEY", "").strip(),
        deepinfra_embedding_model=os.getenv(
            "DEEPINFRA_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-4B"
        ).strip(),
        dense_vector_size=int(os.getenv("DENSE_VECTOR_SIZE", "2560")),
        forge_default_handler=os.getenv("FORGE_DEFAULT_HANDLER", "hyperui").strip().lower() or "hyperui",
        ingest_batch_size=int(os.getenv("INGEST_BATCH_SIZE", "5")),
        ingest_max_retries=int(os.getenv("INGEST_MAX_RETRIES", "3")),
        component_library_root=lib,
    )


def load_settings() -> Settings:
    from tools.paths_config import resolve_component_library_root

    return _settings_for(resolve_component_library_root())


def try_load_settings() -> Settings | None:
    from tools.paths_config import try_resolve_component_library_root

    lib = try_resolve_component_library_root()
    if lib is None:
        return None
    return _settings_for(lib)
