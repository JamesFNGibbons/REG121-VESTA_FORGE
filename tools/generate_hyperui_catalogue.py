"""Generate import_bin/hyperui/catalogue.py from all *.html files on disk (maintainer tool).

Run from repo root after copying HyperUI examples, e.g.:
  python -m tools.generate_hyperui_catalogue
  python -m tools.generate_hyperui_catalogue --library-root /path/to/hyperui

Category is derived from the first path segment, using the same segment→slug map as
ingest category filters (see tools/pipeline.normalize_category).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


# First directory segment → catalogue category (aligned with tools.pipeline._CATEGORY_ALIASES).
_SEGMENT_TO_CATEGORY: dict[str, str] = {
    "heroes": "hero",
    "features": "feature",
    "feature-grids": "feature",
    "footers": "footer",
    "social-proof": "social-proof",
    "cta": "cta",
    "ctas": "cta",
    "contact": "contact",
    "contact-forms": "contact",
    "navigation": "navigation",
}


def _category_for_relative_path(rel: str) -> str:
    seg = rel.split("/", 1)[0]
    return _SEGMENT_TO_CATEGORY.get(seg, seg)


def _default_library_root() -> Path:
    env = os.getenv("COMPONENT_LIBRARY_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "import_bin" / "hyperui"


def _build_catalogue(library_root: Path) -> dict[str, dict[str, str | list[str]]]:
    root = library_root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Library root is not a directory: {root}")
    out: dict[str, dict[str, str | list[str]]] = {}
    for path in sorted(root.rglob("*.html")):
        rel = path.relative_to(root).as_posix()
        cid = rel[: -len(".html")] if rel.endswith(".html") else rel
        out[cid] = {
            "file": rel,
            "category": _category_for_relative_path(rel),
            "handler": "hyperui",
            "source": "hyperui",
            "license": "MIT",
        }
    return out


def _render_python(catalogue: dict[str, dict[str, str | list[str]]]) -> str:
    lines = [
        '"""Auto-generated catalogue of on-disk HyperUI HTML (run tools.generate_hyperui_catalogue)."""',
        "",
        "from __future__ import annotations",
        "",
        "CATALOGUE: dict[str, dict] = {",
    ]
    for cid in sorted(catalogue.keys()):
        lines.append(f"    {cid!r}: {repr(catalogue[cid])},")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Regenerate catalogue.py from *.html under library root.")
    ap.add_argument(
        "--library-root",
        type=Path,
        default=_default_library_root(),
        help="Directory containing catalogue.py sibling and HTML trees (default: import_bin/hyperui).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print entry count only; do not write catalogue.py.",
    )
    args = ap.parse_args()
    root: Path = args.library_root
    cat = _build_catalogue(root)
    if args.dry_run:
        print(f"Would write {len(cat)} entries to {root / 'catalogue.py'}")
        return
    out_path = root / "catalogue.py"
    out_path.write_text(_render_python(cat), encoding="utf-8")
    print(f"Wrote {len(cat)} entries to {out_path}")


if __name__ == "__main__":
    main()
