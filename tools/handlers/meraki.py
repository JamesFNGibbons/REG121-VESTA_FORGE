"""Meraki UI stub — library-specific hooks inherit generic; Forge entry is Generic.preprocess."""

from __future__ import annotations

from tools.handlers.generic import GenericComponentHandler


class MerakiComponentHandler(GenericComponentHandler):
    HANDLER_ID = "meraki"
    DISPLAY_NAME = "Meraki"
    DESCRIPTION = "Stub — uses generic preprocessor."
    LICENSE_NOTE = "MIT — Meraki UI"
    DEFAULT_PALETTE_LABEL = "(stub)"
    STUB = True
