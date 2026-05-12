"""Meraki UI stub — delegates to generic."""

from __future__ import annotations

from tools.handlers.generic import GenericComponentHandler


class MerakiComponentHandler(GenericComponentHandler):
    HANDLER_ID = "meraki"
    DISPLAY_NAME = "Meraki"
    DESCRIPTION = "Stub — uses generic preprocessor."
    LICENSE_NOTE = "MIT — Meraki UI"
    DEFAULT_PALETTE_LABEL = "(stub)"
    STUB = True
