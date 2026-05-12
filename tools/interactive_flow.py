"""Interactive Questionary + Rich flows for library selection and ingest."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from tools.catalogue_loader import load_catalogue
from tools.paths_config import (
    component_library_config_file,
    forge_handler_config_file,
    import_bin_root,
    read_forge_handler_slug,
    repo_root,
    resolve_component_library_root,
    write_forge_handler_slug,
)

console = Console(stderr=True)


def _style() -> questionary.Style:
    return questionary.Style(
        [
            ("qmark", "fg:cyan bold"),
            ("question", "bold"),
            ("answer", "fg:green"),
            ("pointer", "fg:cyan bold"),
            ("highlighted", "fg:cyan bold"),
            ("selected", "fg:green"),
        ]
    )


def prompt_forge_handler_interactive(*, settings: Any) -> str:
    """Questionary: pick handler id; persists to .reg121/forge_handler."""
    from tools.handlers import list_handlers

    style = _style()
    hchoices = [
        f"{h['id']} — {h['name']}" + (" (stub — generic)" if h["stub"] else "") for h in list_handlers()
    ]
    default_h = str(getattr(settings, "forge_default_handler", "hyperui") or "hyperui").lower()
    default_label = next((c for c in hchoices if c.startswith(default_h + " ")), hchoices[0])
    hpick = questionary.select(
        "Which Forge handler / library layout? (sources load from import_bin/<handler>/)",
        choices=hchoices,
        default=default_label,
        style=style,
    ).ask()
    if hpick is None:
        raise click.Abort()
    slug = hpick.split(" — ", 1)[0].strip().lower()
    write_forge_handler_slug(slug)
    return slug


def configure_library_interactive() -> Path:
    """Pick handler (for in-repo import_bin), then path; persist forge_handler + optional component_library_root."""
    style = _style()
    console.print(
        Panel.fit(
            "[bold]Component library[/bold]\n\n"
            "In-repo layout: [cyan]import_bin/<handler>/catalogue.py[/cyan] (e.g. [cyan]import_bin/hyperui/[/cyan]).\n"
            "Pick a handler first, then confirm or edit the absolute path.\n"
            "For a library outside this repo, pick any handler then enter your full path.",
            title="121 · library configure",
            border_style="cyan",
        )
    )

    from tools.settings import load_settings

    settings = load_settings()
    slug = prompt_forge_handler_interactive(settings=settings)

    default_path = str((import_bin_root() / slug).resolve())

    while True:
        raw = questionary.text(
            "Absolute path to directory containing catalogue.py:",
            default=default_path,
            style=style,
        ).ask()
        if raw is None:
            raise click.Abort()
        path = Path(raw.strip()).expanduser().resolve()
        cat = path / "catalogue.py"
        if not cat.is_file():
            console.print(f"[red]✗[/red] Missing [cyan]catalogue.py[/cyan] at {cat}")
            if not questionary.confirm("Try another path?", default=True, style=style).ask():
                raise click.Abort()
            continue

        try:
            cat_dict = load_catalogue(path)
        except Exception as exc:
            console.print(f"[red]✗[/red] Could not load CATALOGUE: {exc}")
            if not questionary.confirm("Try another path?", default=True, style=style).ask():
                raise click.Abort()
            continue

        preview = Table(title="Preview", show_lines=True)
        preview.add_column("id", style="cyan", no_wrap=True)
        preview.add_column("name")
        for _i, (cid, row) in enumerate(sorted(cat_dict.items())[:8]):
            preview.add_row(cid, str(row.get("name", "")))
        if len(cat_dict) > 8:
            preview.add_row("…", f"({len(cat_dict) - 8} more)")
        console.print(preview)

        if not questionary.confirm(
            f"Use this library? ({len(cat_dict)} components, path: {path})",
            default=True,
            style=style,
        ).ask():
            continue

        cfg_dir = repo_root() / ".reg121"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        ib = import_bin_root().resolve()
        pr = path.resolve()
        if pr == ib:
            write_forge_handler_slug(slug)
        elif pr.parent == ib:
            write_forge_handler_slug(pr.name)
        else:
            write_forge_handler_slug(slug)
        cfg_file = component_library_config_file()
        cfg_file.write_text(str(path) + "\n", encoding="utf-8")
        console.print(f"[green]✓[/green] Saved library path to [dim]{cfg_file}[/dim]")
        console.print(f"[green]✓[/green] Handler preference [dim]{forge_handler_config_file()}[/dim] → [bold]{read_forge_handler_slug()}[/bold]")
        console.print(
            Panel(
                "[bold]Next[/bold]\n"
                "  [cyan]./121 build[/cyan]   — rebuild the app image\n"
                "  [cyan]./121 ingest …[/cyan] — run ingestion in Docker\n"
                "  [cyan]./121 validate[/cyan]",
                border_style="green",
            )
        )
        return path


def library_status() -> None:
    try:
        lib_root = resolve_component_library_root()
    except RuntimeError as exc:
        console.print(Panel(str(exc), title="121 · library", border_style="yellow"))
        return

    if not lib_root.is_dir():
        console.print(f"[yellow]Path is not a directory from this environment:[/yellow] {lib_root}")
        return

    try:
        cat = load_catalogue(lib_root)
    except Exception as exc:
        console.print(f"[yellow]Could not load catalogue:[/yellow] {exc}")
        return

    table = Table(title="Component library", show_header=True, header_style="bold")
    table.add_column("Property")
    table.add_column("Value")
    table.add_row("Resolved root", str(lib_root))
    table.add_row("Forge handler file", str(forge_handler_config_file()))
    table.add_row("Forge handler slug", read_forge_handler_slug())
    table.add_row("Components", str(len(cat)))
    cfg = component_library_config_file()
    table.add_row("Library path file", str(cfg) if cfg.is_file() else "(not set)")
    console.print(table)


def run_interactive_ingest_wizard(
    *,
    settings: Any,
    catalogue: dict[str, dict[str, Any]],
) -> tuple[bool, str | None, str | None, bool, bool, bool]:
    """Returns (all_flag, category, single_id, dry_run, skip_enrichment, force). Handler is chosen before wizard."""
    style = _style()
    console.print(
        Panel.fit(
            f"[dim]Library:[/dim] [bold]{settings.component_library_root}[/bold]\n"
            f"[dim]Handler:[/dim] [bold]{read_forge_handler_slug()}[/bold]\n"
            f"[dim]Components:[/dim] [bold]{len(catalogue)}[/bold]",
            title="121 · ingest",
            border_style="magenta",
        )
    )

    scope = questionary.select(
        "What do you want to ingest?",
        choices=[
            "Everything in the catalogue",
            "One category",
            "A single component id",
        ],
        style=style,
    ).ask()
    if scope is None:
        raise click.Abort()

    category: str | None = None
    single_id: str | None = None
    all_flag = False
    if scope == "Everything in the catalogue":
        all_flag = True
    elif scope == "One category":
        cats = sorted({str(row.get("category", "")) for row in catalogue.values() if row.get("category")})
        pick = questionary.select(
            "Pick a category:",
            choices=cats,
            style=style,
        ).ask()
        if pick is None:
            raise click.Abort()
        category = pick
    else:
        keys = sorted(catalogue.keys())
        labels = [f"{k} — {catalogue[k].get('name', '')}" for k in keys]
        pick = questionary.select(
            "Pick a component:",
            choices=labels,
            style=style,
        ).ask()
        if pick is None:
            raise click.Abort()
        single_id = pick.split(" — ", 1)[0]

    dry_run = questionary.confirm("Dry run (no Qdrant writes / no embeddings)?", default=False, style=style).ask()
    if dry_run is None:
        raise click.Abort()
    skip_enrichment = questionary.confirm(
        "Skip Qwen enrichment (catalogue-only embedding text)?",
        default=False,
        style=style,
    ).ask()
    if skip_enrichment is None:
        raise click.Abort()
    force = questionary.confirm("Force re-upsert even if the point already exists?", default=False, style=style).ask()
    if force is None:
        raise click.Abort()

    if not questionary.confirm("Start ingestion now?", default=True, style=style).ask():
        raise click.Abort()

    return all_flag, category, single_id, dry_run, skip_enrichment, force
