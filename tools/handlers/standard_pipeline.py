"""
Ordered Forge stages shared across Tailwind-style handlers.

Call :func:`run_standard_forge` from a handler's :meth:`~tools.handlers.base.ComponentHandler.preprocess`
implementation. Library-specific behaviour lives on the handler (``extract_component``,
``remove_library_artifacts``, ``colour_map``, ``map_colour_class``, ``add_placeholders``); this module only
sequences the shared machinery so stripping and processing stay central to the handler layer.
"""

from __future__ import annotations

from typing import Any

from tools.handlers.colour_replace import apply_tailwind_colour_mapping
from tools.handlers.placeholders import apply_placeholders


def run_standard_forge(handler: Any, raw_html: str) -> tuple[str, dict[str, Any]]:
    """
    Default Forge chain: extract → strip artifacts → Tailwind colour map → handler placeholders
    → shared boilerplate placeholders → report.
    """
    handler._artifact_log = []
    report: dict[str, Any] = {
        "errors": [],
        "extraction_notes": [],
        "artifacts_removed": [],
        "colour_replacements": [],
        "placeholders_added": [],
        "raw_len": len(raw_html),
    }
    try:
        html = handler.extract_component(raw_html)
        report["extraction_notes"].append("extract_component applied")
        report["after_extract_len"] = len(html)
        html = handler.remove_library_artifacts(html)
        report["artifacts_removed"] = list(handler._artifact_log)

        html, colour_rep = apply_tailwind_colour_mapping(html, handler)
        report["colour_replacements"] = colour_rep

        html = handler.add_placeholders(html)

        html, ph_rep = apply_placeholders(html)
        report["placeholders_added"] = ph_rep
        report["final_len"] = len(html)
        merged = handler.get_preprocessing_report(raw_html, html, report)
        return html, merged
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(str(exc))
        merged = handler.get_preprocessing_report(raw_html, raw_html, report)
        return raw_html, merged
