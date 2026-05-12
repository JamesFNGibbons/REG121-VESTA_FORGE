"""Multi-step diagnostic dry-run (distinct from `ingest --dry-run`)."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from tools.embeddings import build_embedding_text, embed_hybrid
from tools.handlers import list_handlers, resolve_handler_for_row
from tools.inspector import inspect_component
from tools.pipeline import pick_sample_ids_per_category
from tools.qdrant_wrapper import DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME, QdrantWrapper

if TYPE_CHECKING:
    from tools.settings import Settings


def run_forge_dry_run(
    *,
    console: Console,
    settings: "Settings",
    catalogue: dict[str, dict[str, Any]],
    handler_cli: str | None,
) -> int:
    """Return 0 if all critical steps pass, else 1."""
    handler, hid = resolve_handler_for_row(
        handler_cli=handler_cli,
        catalogue_row={},
        default_handler_id=settings.forge_default_handler,
    )
    meta = next((h for h in list_handlers() if h["id"] == hid), None)
    title = meta["name"] if meta else hid
    stub_note = " (stub — uses generic preprocessor)" if getattr(handler, "STUB", False) else ""
    console.print(
        Panel.fit(
            f"[bold]Handler:[/bold] {title}{stub_note}\n"
            f"[bold]License:[/bold] {handler.LICENSE_NOTE}\n"
            f"[bold]Default palette:[/bold] {handler.DEFAULT_PALETTE_LABEL}\n"
            f"[bold]Handler id:[/bold] {hid}",
            title="Step 1 — Handler",
            border_style="cyan",
        )
    )

    samples = pick_sample_ids_per_category(catalogue)
    if not samples:
        console.print("[red]No components with categories in catalogue.[/red]")
        return 1

    t = Table(title="Step 2 — One component per category", show_header=True, header_style="bold")
    t.add_column("Category")
    t.add_column("Catalogue id")
    for cat, cid in sorted(samples.items()):
        t.add_row(cat, cid)
    console.print(t)

    prep_ok = 0
    colour_total = 0
    ph_total = 0
    for cat, cid in sorted(samples.items()):
        row = catalogue[cid]
        rel = row.get("file")
        if not rel:
            console.print(f"[yellow]Skip {cid}: no file in catalogue[/yellow]")
            continue
        path = settings.component_library_root / rel
        if not path.is_file():
            console.print(f"[yellow]Skip {cid}: missing {path}[/yellow]")
            continue
        raw = path.read_text(encoding="utf-8")
        hrow, rhid = resolve_handler_for_row(
            handler_cli=handler_cli,
            catalogue_row=row,
            default_handler_id=settings.forge_default_handler,
        )
        proc, rep = hrow.preprocess(raw)
        colour_total += len(rep.get("colour_replacements", []))
        ph_total += len(rep.get("placeholders_added", []))
        errs = rep.get("errors", [])
        ok = len(errs) == 0
        prep_ok += 1 if ok else 0
        lines = [
            f"Raw: {rep.get('raw_len', len(raw))} chars → Processed: {rep.get('processed_len', len(proc))} chars",
            f"Artifacts: {len(rep.get('artifacts_removed', []))}",
            f"Colours replaced: {len(rep.get('colour_replacements', []))}",
            f"Placeholders: {len(rep.get('placeholders_added', []))}",
            f"Alpine preserved: {rep.get('alpine_preserved', False)}",
        ]
        if errs:
            lines.append(f"[red]Errors: {errs}[/red]")
        console.print(
            Panel("\n".join(lines), title=f"Step 3 — {cid}", border_style="green" if ok else "red")
        )

    first_cid = next(iter(sorted(samples.values())))
    first_row = catalogue[first_cid]
    first_path = settings.component_library_root / first_row["file"]
    raw0 = first_path.read_text(encoding="utf-8")
    h0, _ = resolve_handler_for_row(
        handler_cli=handler_cli,
        catalogue_row=first_row,
        default_handler_id=settings.forge_default_handler,
    )
    proc0, _ = h0.preprocess(raw0)

    enrich_ok = False
    enrich_msg = ""
    enrich_elapsed = 0.0
    ins = None
    try:
        t0 = time.perf_counter()
        ins = inspect_component(
            base_url=settings.litellm_base_url,
            api_key=settings.litellm_api_key,
            model=settings.litellm_inspector_model,
            catalogue=first_row,
            html=proc0,
            max_retries=settings.ingest_max_retries,
        )
        enrich_elapsed = time.perf_counter() - t0
        js = json.dumps(ins.model_dump(), indent=2, ensure_ascii=False)
        console.print(Panel(Syntax(js, "json", theme="monokai", word_wrap=True), title="Step 4 — Qwen enrichment", border_style="green"))
        enrich_ok = True
        enrich_msg = f"PASS ({enrich_elapsed:.1f}s)"
    except Exception as exc:  # noqa: BLE001
        enrich_msg = f"FAIL: {exc}"
        console.print(Panel(f"[red]{enrich_msg}[/red]", title="Step 4 — Qwen enrichment", border_style="red"))

    emb_ok = False
    emb_msg = ""
    emb_elapsed = 0.0
    try:
        t0 = time.perf_counter()
        etext = build_embedding_text(
            catalogue=first_row,
            enrichment=ins.model_dump() if ins is not None else None,
        )
        dense, si, sv = embed_hybrid(settings=settings, text=etext)
        emb_elapsed = time.perf_counter() - t0
        nnz = len(si)
        console.print(
            Panel.fit(
                f"Dense len: {len(dense)} (expected {settings.dense_vector_size})\n"
                f"Sparse non-zero: {nnz}\n"
                f"Embedding text chars: {len(etext)}",
                title="Step 5 — Embeddings",
                border_style="green" if len(dense) == settings.dense_vector_size else "yellow",
            )
        )
        emb_ok = len(dense) == settings.dense_vector_size
        emb_msg = f"PASS ({emb_elapsed:.1f}s)"
    except Exception as exc:  # noqa: BLE001
        emb_msg = f"FAIL: {exc}"
        console.print(Panel(f"[red]{emb_msg}[/red]", title="Step 5 — Embeddings", border_style="red"))

    q_ok = False
    q_msg = ""
    try:
        q = QdrantWrapper(
            settings.qdrant_url,
            settings.qdrant_api_key,
            settings.qdrant_collection_name,
            max_retries=settings.ingest_max_retries,
            dense_size=settings.dense_vector_size,
        )
        exists = q.client.collection_exists(settings.qdrant_collection_name)
        if exists:
            cnt = q.client.count(settings.qdrant_collection_name, exact=True).count
            console.print(
                Panel.fit(
                    f"Connected: yes\nCollection exists: yes\nPoints: {cnt}\n"
                    f"Dense vector name: {DENSE_VECTOR_NAME}\nSparse: {SPARSE_VECTOR_NAME}",
                    title="Step 6 — Qdrant",
                    border_style="green",
                )
            )
            q_ok = True
            q_msg = "PASS"
        else:
            q_msg = "collection missing (will be created on first ingest)"
            console.print(Panel.fit(q_msg, title="Step 6 — Qdrant", border_style="yellow"))
            q_ok = True
    except Exception as exc:  # noqa: BLE001
        q_msg = f"FAIL: {exc}"
        console.print(Panel(f"[red]{q_msg}[/red]", title="Step 6 — Qdrant", border_style="red"))

    ready = prep_ok == len(samples) and enrich_ok and emb_ok and q_ok
    st = Table(title=f"Step 7 — Dry run summary ({hid})", show_header=True)
    st.add_column("Check")
    st.add_column("Result")
    st.add_row("Components sampled", str(len(samples)))
    st.add_row("Preprocessing rows", f"{prep_ok}/{len(samples)}")
    st.add_row("Colour replacements (total)", str(colour_total))
    st.add_row("Placeholders (total)", str(ph_total))
    st.add_row("Qwen enrichment", enrich_msg)
    st.add_row("Embeddings", emb_msg)
    st.add_row("Qdrant", q_msg)
    st.add_row("Ready to ingest?", "YES" if ready else "NO")
    console.print(st)
    return 0 if ready else 1
