"""Flowbite stub — library-specific hooks inherit generic; Forge entry is Generic.preprocess."""

from __future__ import annotations

from tools.handlers.generic import GenericComponentHandler


class FlowbiteComponentHandler(GenericComponentHandler):
    HANDLER_ID = "flowbite"
    DISPLAY_NAME = "Flowbite"
    DESCRIPTION = "Stub — uses generic preprocessor."
    LICENSE_NOTE = "MIT — Flowbite"
    DEFAULT_PALETTE_LABEL = "(stub)"
    STUB = True
