"""Resolve REG121 repo root and external component library location."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    env = os.getenv("REG121_REPO_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def component_library_config_file() -> Path:
    return repo_root() / ".reg121" / "component_library_root"


def import_bin_root() -> Path:
    """Default in-repo directory for catalogue.py + HTML (mounted at /library in Docker)."""
    return repo_root() / "import_bin"


def resolve_component_library_root() -> Path:
    """Resolve directory containing catalogue.py and HTML (host path, mounted at /library in Docker)."""
    raw = os.getenv("COMPONENT_LIBRARY_ROOT", "").strip()
    if not raw:
        cfg = component_library_config_file()
        if cfg.is_file():
            raw = cfg.read_text(encoding="utf-8").strip()
    if not raw:
        imp = import_bin_root()
        if (imp / "catalogue.py").is_file():
            return imp.resolve()
        raise RuntimeError(
            "Component library is not configured.\n"
            "  • Populate import_bin/ with catalogue.py and HTML (see examples/component-library-starter/), or\n"
            "  • Set COMPONENT_LIBRARY_ROOT, or\n"
            "  • Run: ./121 library configure\n"
        )
    return Path(raw).expanduser().resolve()


def try_resolve_component_library_root() -> Path | None:
    try:
        return resolve_component_library_root()
    except RuntimeError:
        return None
