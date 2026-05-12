"""Load CATALOGUE dict from an external component library directory."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


def load_catalogue_module(library_root: Path) -> ModuleType:
    root = library_root.expanduser().resolve()
    cat_file = root / "catalogue.py"
    if not cat_file.is_file():
        raise FileNotFoundError(f"Expected catalogue.py at {cat_file}")

    spec = importlib.util.spec_from_file_location(
        "reg121_external_component_catalogue",
        cat_file,
        submodule_search_locations=[str(root)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load catalogue from {cat_file}")

    inserted = False
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)
        inserted = True
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if inserted:
            try:
                sys.path.remove(root_s)
            except ValueError:
                pass

    return mod


def load_catalogue(library_root: Path) -> dict[str, dict[str, Any]]:
    mod = load_catalogue_module(library_root)
    if not hasattr(mod, "CATALOGUE"):
        raise ValueError(f"catalogue.py at {library_root} must define CATALOGUE dict")
    cat = getattr(mod, "CATALOGUE")
    if not isinstance(cat, dict):
        raise TypeError("CATALOGUE must be a dict")
    return cat
