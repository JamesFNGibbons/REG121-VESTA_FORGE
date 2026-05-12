"""Click CLI entry point for component ingestion."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.console import Console

from tools.catalogue_loader import load_catalogue
from tools.interactive_flow import configure_library_interactive, library_status, run_interactive_ingest_wizard
from tools.pipeline import normalize_category, resolve_catalogue_ids, run_ingest
from tools.qdrant_wrapper import QdrantWrapper
from tools.settings import load_settings
from tools import validate as validate_mod

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
console = Console(stderr=True)


def _ensure_repo_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version="1.0.0", prog_name="121 ingest")
def cli() -> None:
    """REG121 design-brain component ingestion for Qdrant Cloud."""


@cli.group("library")
def library_cli() -> None:
    """Inspect or configure the external component library (outside this repo)."""


@library_cli.command("configure")
def library_configure_cmd() -> None:
    """Interactively pick and confirm a component library directory."""
    _ensure_repo_on_path()
    configure_library_interactive()


@library_cli.command("status")
def library_status_cmd() -> None:
    """Show resolved library path and catalogue size."""
    _ensure_repo_on_path()
    library_status()


@cli.command("ingest")
@click.option("--all", "all_flag", is_flag=True, help="Ingest every catalogue entry.")
@click.option("--category", type=str, default=None, help="Filter by catalogue category (e.g. hero, feature).")
@click.option("--id", "single_id", type=str, default=None, help="Single catalogue id (e.g. heroes/split-left).")
@click.option("--dry-run", is_flag=True, help="Run checks and enrichment but do not write to Qdrant.")
@click.option("--force", is_flag=True, help="Upsert even if the point already exists.")
@click.option("--skip-enrichment", is_flag=True, help="Skip LiteLLM/Qwen; embeddings use catalogue text only.")
@click.option(
    "--interactive",
    "interactive",
    is_flag=True,
    help="Guided prompts (scope, dry-run, force). Implies TTY; use when no ingest flags are passed.",
)
def ingest_cmd(
    all_flag: bool,
    category: str | None,
    single_id: str | None,
    dry_run: bool,
    force: bool,
    skip_enrichment: bool,
    interactive: bool,
) -> None:
    _ensure_repo_on_path()
    settings = load_settings()
    catalogue = load_catalogue(settings.component_library_root)

    use_all, use_category, use_id = all_flag, category, single_id
    use_dry, use_skip, use_force = dry_run, skip_enrichment, force

    selection_count = sum(bool(x) for x in (use_all, use_category, use_id))
    if interactive and selection_count > 0:
        raise click.UsageError("Do not combine --interactive with --all, --category, or --id.")

    if interactive or selection_count == 0:
        if not sys.stdin.isatty():
            raise click.UsageError("Interactive mode requires a TTY (use --all, --category, or --id).")
        a, c, i, dr, se, ff = run_interactive_ingest_wizard(settings=settings, catalogue=catalogue)
        use_all, use_category, use_id, use_dry, use_skip, use_force = a, c, i, dr, se, ff
    elif selection_count != 1:
        raise click.UsageError("Choose exactly one of: --all, --category, --id (or use --interactive).")

    if not settings.qdrant_url or not settings.qdrant_api_key:
        raise click.UsageError("QDRANT_URL and QDRANT_API_KEY are required for ingest.")

    if not use_dry and not settings.openai_api_key:
        raise click.UsageError("OPENAI_API_KEY is required unless using --dry-run.")

    if not use_skip and not settings.litellm_api_key:
        raise click.UsageError("LITELLM_API_KEY is required unless --skip-enrichment.")

    ids = resolve_catalogue_ids(
        catalogue=catalogue,
        all_flag=use_all,
        category=use_category,
        single_id=use_id,
    )

    qdrant = QdrantWrapper(
        settings.qdrant_url,
        settings.qdrant_api_key,
        settings.qdrant_collection_name,
        max_retries=settings.ingest_max_retries,
    )
    if not use_dry:
        qdrant.ensure_collection()
        qdrant.ensure_payload_indexes()

    run_ingest(
        settings=settings,
        qdrant=qdrant,
        catalogue=catalogue,
        ids=ids,
        dry_run=use_dry,
        force=use_force,
        skip_enrichment=use_skip,
    )


@cli.command("stats")
def stats_cmd() -> None:
    _ensure_repo_on_path()
    settings = load_settings()
    if not settings.qdrant_url or not settings.qdrant_api_key:
        raise click.UsageError("QDRANT_URL and QDRANT_API_KEY are required.")

    qdrant = QdrantWrapper(
        settings.qdrant_url,
        settings.qdrant_api_key,
        settings.qdrant_collection_name,
        max_retries=settings.ingest_max_retries,
    )
    from rich.table import Table

    if not qdrant.client.collection_exists(settings.qdrant_collection_name):
        console.print(f"[yellow]Collection '{settings.qdrant_collection_name}' does not exist yet.[/yellow]")
        return

    info = qdrant.collection_stats()
    table = Table(title="Qdrant collection", show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Collection", str(info.get("name")))
    table.add_row("Points (exact count)", str(info.get("points_count")))
    table.add_row("Dense vectors config", str(info.get("dense_config")))
    table.add_row("Sparse vectors config", str(info.get("sparse_vectors_config")))
    payload_schema = info.get("payload_schema")
    if payload_schema:
        keys = ", ".join(sorted(payload_schema.keys()))
        table.add_row("Payload indexes", keys[:500] + ("…" if len(keys) > 500 else ""))
    else:
        table.add_row("Payload indexes", "(none reported)")
    console.print(table)


@cli.command("search")
@click.option("--query", required=True, type=str, help="Natural language query.")
@click.option("--category", type=str, default=None, help="Optional category filter (e.g. hero).")
@click.option("--limit", type=int, default=10, show_default=True)
def search_cmd(query: str, category: str | None, limit: int) -> None:
    _ensure_repo_on_path()
    settings = load_settings()
    if not settings.openai_api_key:
        raise click.UsageError("OPENAI_API_KEY is required for search.")
    if not settings.qdrant_url or not settings.qdrant_api_key:
        raise click.UsageError("QDRANT_URL and QDRANT_API_KEY are required.")

    from rich.table import Table

    from tools.embeddings import embed_hybrid

    qdrant = QdrantWrapper(
        settings.qdrant_url,
        settings.qdrant_api_key,
        settings.qdrant_collection_name,
        max_retries=settings.ingest_max_retries,
    )
    dense, s_idx, s_val = embed_hybrid(openai_api_key=settings.openai_api_key, text=query)
    cat = normalize_category(category) if category else None
    hits = qdrant.hybrid_search(
        dense_query=dense,
        sparse_indices=s_idx,
        sparse_values=s_val,
        limit=limit,
        category=cat,
    )
    table = Table(title="Hybrid search results", show_header=True, header_style="bold")
    table.add_column("Score", justify="right")
    table.add_column("Point id")
    table.add_column("Catalogue id")
    table.add_column("Name")
    table.add_column("Category")
    for h in hits:
        pl = h.payload or {}
        table.add_row(
            f"{h.score:.4f}" if h.score is not None else "",
            str(h.id),
            str(pl.get("catalogue_id", "")),
            str(pl.get("name", "")),
            str(pl.get("category", "")),
        )
    console.print(table)


@cli.command("validate")
def validate_cmd() -> None:
    _ensure_repo_on_path()
    validate_mod.run_validate(console=console)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
