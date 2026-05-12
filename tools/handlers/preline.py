"""Preline UI stub — library-specific hooks inherit generic; Forge entry is Generic.preprocess."""

from __future__ import annotations

from tools.handlers.generic import GenericComponentHandler


class PrelineComponentHandler(GenericComponentHandler):
    HANDLER_ID = "preline"
    DISPLAY_NAME = "Preline"
    DESCRIPTION = "Stub — uses generic preprocessor."
    LICENSE_NOTE = "MIT — Preline UI"
    DEFAULT_PALETTE_LABEL = "(stub)"
    STUB = True
