"""Resolve REG121 repo root and component library location (import_bin/<handler> layout)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def repo_root() -> Path:
    env = os.getenv("REG121_REPO_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def component_library_config_file() -> Path:
    return repo_root() / ".reg121" / "component_library_root"


def forge_handler_config_file() -> Path:
    """Persists handler id (e.g. hyperui) for import_bin/<handler>/ resolution."""
    return repo_root() / ".reg121" / "forge_handler"


def import_bin_root() -> Path:
    """Parent directory: import_bin/<handler_id>/ each hold a catalogue."""
    return repo_root() / "import_bin"


def read_forge_handler_slug() -> str:
    """Handler subdirectory under import_bin/ (from wizard, CLI, or env)."""
    cfg = forge_handler_config_file()
    if cfg.is_file():
        s = cfg.read_text(encoding="utf-8").strip().lower()
        if s:
            return s
    return os.getenv("FORGE_DEFAULT_HANDLER", "hyperui").strip().lower() or "hyperui"


def write_forge_handler_slug(slug: str) -> None:
    d = repo_root() / ".reg121"
    d.mkdir(parents=True, exist_ok=True)
    forge_handler_config_file().write_text(slug.strip().lower() + "\n", encoding="utf-8")


def _import_bin_library_path_for_slug(slug: str) -> Path | None:
    """Return import_bin/<slug> if catalogue exists; else sensible fallbacks."""
    base = import_bin_root()
    sub = base / slug
    if (sub / "catalogue.py").is_file():
        return sub.resolve()
    if slug != "hyperui" and (base / "hyperui" / "catalogue.py").is_file():
        logger.warning(
            "import_bin/%s has no catalogue.py; using import_bin/hyperui (copy or add a library there).",
            slug,
        )
        return (base / "hyperui").resolve()
    if (base / "catalogue.py").is_file():
        logger.warning("Using legacy flat import_bin/ (no handler subdirectory). Prefer import_bin/<handler>/.")
        return base.resolve()
    return None


def resolve_component_library_root() -> Path:
    """Directory containing catalogue.py (often import_bin/<handler>/)."""
    raw = os.getenv("COMPONENT_LIBRARY_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()

    cfg = component_library_config_file()
    if cfg.is_file():
        p = Path(cfg.read_text(encoding="utf-8").strip()).expanduser().resolve()
        if p.is_dir() and (p / "catalogue.py").is_file():
            return p

    slug = read_forge_handler_slug()
    resolved = _import_bin_library_path_for_slug(slug)
    if resolved is not None:
        return resolved

    raise RuntimeError(
        "Component library is not configured.\n"
        "  • Add catalogue under import_bin/<handler>/ (e.g. import_bin/hyperui/), or\n"
        "  • Set COMPONENT_LIBRARY_ROOT, or\n"
        "  • Run: ./121 library configure\n"
        "Pick a handler in the ingest interactive wizard or set FORGE_DEFAULT_HANDLER."
    )


def try_resolve_component_library_root() -> Path | None:
    try:
        return resolve_component_library_root()
    except RuntimeError:
        return None
