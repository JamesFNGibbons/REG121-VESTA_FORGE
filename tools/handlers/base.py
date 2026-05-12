"""
Abstract base for library-specific HTML preprocessing (Forge).

Orchestration for the default MIT/Tailwind pipeline lives in
:mod:`tools.handlers.standard_pipeline` and is invoked from
:class:`tools.handlers.generic.GenericComponentHandler` (and subclasses). Ingest and dry-run only
mutate HTML via :meth:`ComponentHandler.preprocess` on the resolved handler — no stripping or
processing elsewhere.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ComponentHandler(ABC):
    """Pluggable preprocessor for Tailwind component HTML before enrichment / ingest."""

    HANDLER_ID: str = "generic"
    DISPLAY_NAME: str = "Generic"
    DESCRIPTION: str = "Best-effort extraction and brand token mapping."
    LICENSE_NOTE: str = "Varies by source library"
    DEFAULT_PALETTE_LABEL: str = "multi"
    STUB: bool = False

    def __init__(self) -> None:
        self._artifact_log: list[str] = []

    def _note_artifact(self, message: str) -> None:
        self._artifact_log.append(message)

    @abstractmethod
    def extract_component(self, raw_html: str) -> str:
        """Strip full-document wrapper; return component fragment HTML."""

    @abstractmethod
    def remove_library_artifacts(self, html: str) -> str:
        """Remove library-specific CSS/JS references; call _note_artifact when removing."""

    @abstractmethod
    def colour_map(self) -> dict[str, str]:
        """Logical role -> CSS var(), e.g. primary -> var(--brand-primary)."""

    @abstractmethod
    def add_placeholders(self, html: str) -> str:
        """Replace boilerplate content with [[PLACEHOLDER]] tokens (optional no-op wrapper)."""

    def map_colour_class(self, token: str, element: Any = None) -> tuple[dict[str, str], list[str]] | None:
        """
        If token is a Tailwind colour utility to replace, return (style_props, tokens_to_remove).
        style_props keys: color, background, border_color.
        Otherwise return None.
        """
        return None

    @abstractmethod
    def preprocess(self, raw_html: str) -> tuple[str, dict[str, Any]]:
        """
        Full Forge pipeline for one component file. Implement by delegating to
        :func:`tools.handlers.standard_pipeline.run_standard_forge` or a custom chain; ingest/dry-run
        call only this method for HTML transformation.
        """

    def get_preprocessing_report(
        self, raw: str, processed: str, pipeline_report: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        pr = pipeline_report or {}
        return {
            "handler_id": self.HANDLER_ID,
            "raw_len": pr.get("raw_len", len(raw)),
            "processed_len": pr.get("final_len", len(processed)),
            "errors": pr.get("errors", []),
            "extraction_notes": pr.get("extraction_notes", []),
            "artifacts_removed": pr.get("artifacts_removed", []),
            "colour_replacements": pr.get("colour_replacements", []),
            "placeholders_added": pr.get("placeholders_added", []),
            "alpine_preserved": "x-data" in processed or "@click" in processed or ":class" in processed,
        }
