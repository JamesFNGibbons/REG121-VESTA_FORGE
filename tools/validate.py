"""Pre-flight checks for environment variables and remote services."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from rich.panel import Panel

from tools.catalogue_loader import load_catalogue
from tools.qdrant_wrapper import DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME, QdrantWrapper
from tools.settings import try_load_settings

if TYPE_CHECKING:
    from rich.console import Console

logger = logging.getLogger(__name__)


def run_validate(*, console: "Console") -> None:
    settings = try_load_settings()
    issues: list[str] = []

    if settings is None:
        console.print(
            Panel(
                "Run [cyan]./121 library configure[/cyan] (host) or [cyan]library configure[/cyan] inside the "
                "container, or set [bold]COMPONENT_LIBRARY_ROOT[/bold].\n"
                "By default the repo uses [bold]import_bin/[/bold] (see examples/component-library-starter/).",
                title="Component library not configured",
                border_style="yellow",
            )
        )
    else:
        if not settings.component_library_root.is_dir():
            issues.append(f"COMPONENT_LIBRARY_ROOT is not a directory: {settings.component_library_root}")
        else:
            try:
                cat = load_catalogue(settings.component_library_root)
                console.print(f"[green]Catalogue:[/green] loaded [bold]{len(cat)}[/bold] entries from {settings.component_library_root}")
            except Exception as exc:
                issues.append(f"Catalogue load failed: {exc}")

    if settings:
        if not settings.qdrant_url:
            issues.append("QDRANT_URL is not set")
        if not settings.qdrant_api_key:
            issues.append("QDRANT_API_KEY is not set")
        if not settings.deepinfra_api_key:
            issues.append("DEEPINFRA_API_KEY is not set (required for embeddings and search)")
        if not settings.litellm_api_key:
            issues.append(
                "LITELLM_API_KEY is not set (required for enrichment unless you always use --skip-enrichment)"
            )
        if settings.dense_vector_size < 1:
            issues.append("DENSE_VECTOR_SIZE must be >= 1")

        if settings.ingest_batch_size < 1:
            issues.append("INGEST_BATCH_SIZE must be >= 1")
        if settings.ingest_max_retries < 1:
            issues.append("INGEST_MAX_RETRIES must be >= 1")

    if settings and issues:
        console.print("[yellow]Configuration warnings:[/yellow]")
        for it in issues:
            console.print(f"  - {it}")
    elif settings and not issues:
        console.print("[green]Core environment variables present.[/green]")

    q_url = os.getenv("QDRANT_URL", "").strip() if settings is None else settings.qdrant_url
    q_key = os.getenv("QDRANT_API_KEY", "").strip() if settings is None else settings.qdrant_api_key
    q_coll = os.getenv("QDRANT_COLLECTION_NAME", "reg121_design_brain").strip() if settings is None else settings.qdrant_collection_name
    max_retries = int(os.getenv("INGEST_MAX_RETRIES", "3")) if settings is None else settings.ingest_max_retries
    dense_sz = int(os.getenv("DENSE_VECTOR_SIZE", "2560")) if settings is None else settings.dense_vector_size

    if q_url and q_key:
        try:
            q = QdrantWrapper(q_url, q_key, q_coll, max_retries=max_retries, dense_size=dense_sz)
            if not q.client.collection_exists(q_coll):
                console.print(
                    f"[yellow]Qdrant: collection '{q_coll}' does not exist yet "
                    f"(it will be created on first ingest).[/yellow]"
                )
            else:
                info = q.client.get_collection(q_coll)
                console.print(f"[green]Qdrant: connected; collection '{q_coll}' exists.[/green]")
                params = info.config.params
                vectors = params.vectors
                if isinstance(vectors, dict):
                    dense_cfg = vectors.get(DENSE_VECTOR_NAME)
                else:
                    dense_cfg = vectors
                if dense_cfg is None:
                    console.print("[red]Qdrant: missing dense vector config.[/red]")
                else:
                    size = getattr(dense_cfg, "size", None)
                    if size != dense_sz:
                        console.print(
                            f"[red]Qdrant: dense vector size is {size}, expected {dense_sz} (DENSE_VECTOR_SIZE).[/red]"
                        )
                    else:
                        console.print(
                            f"[green]Qdrant: dense vector '{DENSE_VECTOR_NAME}' size OK ({dense_sz}).[/green]"
                        )
                sparse = getattr(params, "sparse_vectors", None)
                if not sparse or SPARSE_VECTOR_NAME not in (sparse or {}):
                    console.print(
                        f"[yellow]Qdrant: sparse vector '{SPARSE_VECTOR_NAME}' not found in collection config.[/yellow]"
                    )
                else:
                    console.print(f"[green]Qdrant: sparse vector '{SPARSE_VECTOR_NAME}' configured.[/green]")

                if info.payload_schema:
                    console.print(
                        f"[green]Qdrant: payload schema has {len(info.payload_schema)} indexed field(s).[/green]"
                    )
                else:
                    console.print("[yellow]Qdrant: no payload indexes reported (run ingest to create them).[/yellow]")

                sample = q.scroll_sample(limit=1)
                if sample:
                    console.print(f"[green]Qdrant: sample scroll returned {len(sample)} point(s).[/green]")
                else:
                    console.print("[dim]Qdrant: collection is empty (no points yet).[/dim]")
        except Exception as exc:
            console.print(f"[red]Qdrant connectivity failed: {exc}[/red]")
            logger.exception("Qdrant validate")

    litellm_key = os.getenv("LITELLM_API_KEY", "").strip() if settings is None else settings.litellm_api_key
    litellm_base = (
        os.getenv("LITELLM_BASE_URL", "https://litellm.ai.reg121.com").strip().rstrip("/")
        if settings is None
        else settings.litellm_base_url
    )
    if litellm_key and litellm_base:
        try:
            from openai import OpenAI

            root = litellm_base.rstrip("/")
            if not root.endswith("/v1"):
                root = root + "/v1"
            oc = OpenAI(base_url=root, api_key=litellm_key)
            models = oc.models.list()
            _ = models.data
            console.print("[green]LiteLLM: OpenAI-compatible /v1/models reachable.[/green]")
        except Exception as exc:
            console.print(f"[yellow]LiteLLM probe failed (non-fatal): {exc}[/yellow]")
            logger.info("LiteLLM probe failed", exc_info=True)

    if settings is not None and settings.deepinfra_api_key:
        try:
            from tools.embeddings import embed_dense

            _ = embed_dense(
                base_url=settings.deepinfra_base_url,
                api_key=settings.deepinfra_api_key,
                embedding_model=settings.deepinfra_embedding_model,
                expected_dim=settings.dense_vector_size,
                text="validate",
            )
            console.print(
                f"[green]DeepInfra: embedding probe OK ({settings.deepinfra_embedding_model}, dim={settings.dense_vector_size}).[/green]"
            )
        except Exception as exc:
            console.print(f"[yellow]DeepInfra embedding probe failed (non-fatal): {exc}[/yellow]")
            logger.info("DeepInfra embedding probe failed", exc_info=True)

    console.print("[bold]Validate finished.[/bold]")
