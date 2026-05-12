"""Ingestion orchestration, Rich progress, and payload assembly."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

from tools.embeddings import build_embedding_text, embed_hybrid
from tools.handlers import resolve_handler_for_row
from tools.inspector import InspectionResult, inspect_component, inspection_to_payload_dict
from tools.qdrant_wrapper import QdrantWrapper, point_id_for_catalogue_key
from tools.settings import Settings

logger = logging.getLogger(__name__)

console = Console(stderr=True)


def _short_id(catalogue_id: str, *, max_len: int = 42) -> str:
    if len(catalogue_id) <= max_len:
        return catalogue_id
    return catalogue_id[: max_len - 1] + "…"

_CATEGORY_ALIASES: dict[str, str] = {
    "heroes": "hero",
    "hero": "hero",
    "features": "feature",
    "feature": "feature",
    "footers": "footer",
    "footer": "footer",
    "social-proof": "social-proof",
    "socialproof": "social-proof",
    "social": "social-proof",
    "cta": "cta",
    "contact": "contact",
    "navigation": "navigation",
}


def normalize_category(user: str) -> str:
    k = user.strip().lower()
    return _CATEGORY_ALIASES.get(k, k)


def resolve_catalogue_ids(
    *,
    catalogue: dict[str, dict[str, Any]],
    all_flag: bool,
    category: str | None,
    single_id: str | None,
) -> list[str]:
    if single_id:
        if single_id not in catalogue:
            raise click.ClickException(f"Unknown catalogue id: {single_id}")
        return [single_id]
    if category:
        cat = normalize_category(category)
        ids = [cid for cid, row in catalogue.items() if row.get("category") == cat]
        if not ids:
            raise click.ClickException(f"No components for category: {category} (resolved: {cat})")
        return sorted(ids)
    if all_flag:
        return sorted(catalogue.keys())
    raise click.ClickException("Specify one of --all, --category, or --id")


def pick_sample_ids_per_category(catalogue: dict[str, dict[str, Any]]) -> dict[str, str]:
    """One deterministic catalogue id per normalized category (for dry-run matrix)."""
    buckets: dict[str, list[str]] = {}
    for cid, row in catalogue.items():
        cat = str(row.get("category") or "").strip().lower()
        if not cat:
            continue
        ncat = normalize_category(cat)
        buckets.setdefault(ncat, []).append(cid)
    return {k: sorted(v)[0] for k, v in sorted(buckets.items()) if v}


# TODO: remove or make configurable post-launch — html_raw is for debugging preprocessor output only.
_HTML_RAW_DEBUG_CAP = 10_000


def _assemble_payload(
    *,
    catalogue_id: str,
    catalogue_row: dict[str, Any],
    html: str,
    html_raw: str,
    forge_handler: str,
    inspection: InspectionResult,
    embedding_text: str,
) -> dict[str, Any]:
    enrichment = inspection.model_dump()
    merged_index = inspection_to_payload_dict(inspection)
    # TODO: remove or make configurable post-launch.
    html_raw_capped = (html_raw or "")[:_HTML_RAW_DEBUG_CAP]
    return {
        "catalogue_id": catalogue_id,
        "point_id": point_id_for_catalogue_key(catalogue_id),
        **catalogue_row,
        "forge_handler": forge_handler,
        "enrichment": enrichment,
        "emotional_trust": merged_index["emotional_trust"],
        "emotional_authority": merged_index["emotional_authority"],
        "emotional_warmth": merged_index["emotional_warmth"],
        "js_type": merged_index["js_type"],
        "js_complexity": merged_index["js_complexity"],
        "price_point_signal": merged_index["price_point_signal"],
        "conversion_role": merged_index["conversion_role"],
        "layout_pattern": merged_index["layout_pattern"],
        "js_dependencies": merged_index["js_dependencies"],
        "html": html,
        "html_raw": html_raw_capped,
        "html_preview": html[:500],
        "embedding_text": embedding_text,
        "usage_count": 0,
        "acceptance_rate": 0.5,
        "edit_frequency": 0.0,
    }


def run_ingest(
    *,
    settings: Settings,
    qdrant: QdrantWrapper,
    catalogue: dict[str, dict[str, Any]],
    ids: list[str],
    dry_run: bool,
    force: bool,
    skip_enrichment: bool,
    handler_cli: str | None = None,
    wizard_handler_id: str | None = None,
) -> dict[str, int]:
    lib_root: Path = settings.component_library_root
    counts: dict[str, int] = {"ingested": 0, "skipped": 0, "failed": 0}
    t0 = time.perf_counter()

    progress_columns = (
        SpinnerColumn(style="cyan"),
        TextColumn("[bold]{task.fields[cid]}[/bold] [dim]{task.fields[step]}[/dim]", justify="left"),
        BarColumn(complete_style="green", finished_style="green"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(compact=True),
    )

    batch = max(1, settings.ingest_batch_size)
    batches = [ids[i : i + batch] for i in range(0, len(ids), batch)]

    with Progress(*progress_columns, console=console, transient=False, expand=True) as progress:
        task = progress.add_task("", total=len(ids), cid="", step="starting…")
        for bi, batch_ids in enumerate(batches):
            if len(batches) > 1:
                progress.console.rule(f"[dim]Batch {bi + 1}/{len(batches)} ({len(batch_ids)} components)[/dim]")
            for catalogue_id in batch_ids:
                row = catalogue[catalogue_id]
                sid = _short_id(catalogue_id)

                def _set_step(label: str) -> None:
                    progress.update(task, fields={"cid": sid, "step": label})

                def step(msg: str, *, cid: str = catalogue_id) -> None:
                    progress.console.log(Text(cid, style="bold") + Text(f" → {msg}", style="dim"))

                try:
                    _set_step("checking…")
                    step("checking…")
                    if not force and qdrant.point_exists(catalogue_id):
                        counts["skipped"] += 1
                        _set_step("skipped (already in Qdrant)")
                        progress.console.print(
                            Text(catalogue_id, style="bold")
                            + Text(" ✓ ", style="yellow")
                            + Text("skipped (already in Qdrant)", style="yellow")
                        )
                    else:
                        _set_step("loading HTML…")
                        step("loading HTML…")
                        rel = Path(row["file"])
                        path = lib_root / rel
                        if not path.is_file():
                            raise FileNotFoundError(f"Missing HTML file: {path}")

                        html_raw = path.read_text(encoding="utf-8")
                        eff_cli = handler_cli or wizard_handler_id
                        handler, hid = resolve_handler_for_row(
                            handler_cli=eff_cli,
                            catalogue_row=row,
                            default_handler_id=settings.forge_default_handler,
                        )
                        processed, prep_report = handler.preprocess(html_raw)
                        n_art = len(prep_report.get("artifacts_removed", []))
                        n_col = len(prep_report.get("colour_replacements", []))
                        n_ph = len(prep_report.get("placeholders_added", []))
                        step(
                            f"preprocess ({hid}): artifacts={n_art}, colours={n_col}, placeholders={n_ph}"
                        )

                        if skip_enrichment:
                            _set_step("enrich (skipped)…")
                            step("enriching with Qwen… (skipped)")
                            inspection = InspectionResult()
                            embedding_text = build_embedding_text(catalogue=row, enrichment=None)
                        else:
                            _set_step("enriching (Qwen, may be slow)…")
                            step("enriching with Qwen…")
                            inspection = inspect_component(
                                base_url=settings.litellm_base_url,
                                api_key=settings.litellm_api_key,
                                model=settings.litellm_inspector_model,
                                catalogue=row,
                                html=processed,
                                max_retries=settings.ingest_max_retries,
                            )
                            embedding_text = build_embedding_text(
                                catalogue=row,
                                enrichment=inspection.model_dump(),
                            )

                        _set_step("embeddings (DeepInfra + SPLADE)…")
                        step("generating embeddings…")
                        if dry_run:
                            _set_step("dry-run (no store)…")
                            step("storing in Qdrant… (dry-run)")
                            counts["ingested"] += 1
                            progress.console.print(
                                Text(catalogue_id, style="bold")
                                + Text(" ✓ ", style="green")
                                + Text("dry-run OK", style="green")
                            )
                        else:
                            dense, s_idx, s_val = embed_hybrid(settings=settings, text=embedding_text)

                            _set_step("storing in Qdrant…")
                            step("storing in Qdrant…")
                            payload = _assemble_payload(
                                catalogue_id=catalogue_id,
                                catalogue_row=row,
                                html=processed,
                                html_raw=html_raw,
                                forge_handler=hid,
                                inspection=inspection,
                                embedding_text=embedding_text,
                            )
                            qdrant.upsert_component(
                                catalogue_id=catalogue_id,
                                dense=dense,
                                sparse_indices=s_idx,
                                sparse_values=s_val,
                                payload=payload,
                            )
                            counts["ingested"] += 1
                            progress.console.print(
                                Text(catalogue_id, style="bold")
                                + Text(" ✓ ", style="green")
                                + Text("ingested", style="green")
                            )
                except Exception as exc:
                    counts["failed"] += 1
                    logger.exception("Failed %s", catalogue_id)
                    progress.console.print(
                        Text(catalogue_id, style="bold") + Text(" ✗ ", style="red") + Text(str(exc), style="red")
                    )
                finally:
                    progress.advance(task)

    elapsed = time.perf_counter() - t0
    table = Table(title="Ingest summary", show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Ingested", str(counts["ingested"]))
    table.add_row("Skipped", str(counts["skipped"]))
    table.add_row("Failed", str(counts["failed"]))
    table.add_row("Elapsed (s)", f"{elapsed:.1f}")
    console.print(table)
    return counts
