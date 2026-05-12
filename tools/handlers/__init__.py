"""
Registered component library handlers (Forge).

All HTML stripping and preprocessing for ingest/dry-run flows through the resolved handler's
:meth:`tools.handlers.base.ComponentHandler.preprocess`. Shared sequencing lives in
:mod:`tools.handlers.standard_pipeline`; shared primitives in ``colour_replace`` and ``placeholders``.
"""

from __future__ import annotations

import logging
from typing import Any

from tools.handlers.base import ComponentHandler
from tools.handlers.flowbite import FlowbiteComponentHandler
from tools.handlers.generic import GenericComponentHandler
from tools.handlers.hyperui import HyperUIComponentHandler
from tools.handlers.meraki import MerakiComponentHandler
from tools.handlers.preline import PrelineComponentHandler

logger = logging.getLogger(__name__)

_HANDLER_CLASSES: tuple[type[ComponentHandler], ...] = (
    HyperUIComponentHandler,
    FlowbiteComponentHandler,
    PrelineComponentHandler,
    MerakiComponentHandler,
    GenericComponentHandler,
)

_HANDLERS: dict[str, type[ComponentHandler]] = {cls.HANDLER_ID: cls for cls in _HANDLER_CLASSES}


def list_handlers() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cls in _HANDLER_CLASSES:
        stub = getattr(cls, "STUB", False)
        out.append(
            {
                "id": cls.HANDLER_ID,
                "name": cls.DISPLAY_NAME,
                "description": cls.DESCRIPTION,
                "license": cls.LICENSE_NOTE,
                "palette": cls.DEFAULT_PALETTE_LABEL,
                "stub": stub,
                "implementation": (
                    "stub — uses generic preprocessor" if stub else "native"
                ),
            }
        )
    return out


def get_handler(handler_id: str) -> ComponentHandler:
    key = (handler_id or "").strip().lower()
    cls = _HANDLERS.get(key)
    if cls is None:
        logger.warning("Unknown handler %r; using generic", handler_id)
        return GenericComponentHandler()
    return cls()


def resolve_handler_for_row(
    *,
    handler_cli: str | None,
    catalogue_row: dict[str, Any],
    default_handler_id: str,
) -> tuple[ComponentHandler, str]:
    """
    Resolution: --handler > catalogue handler > FORGE_DEFAULT_HANDLER (from settings) > generic fallback.
    """
    if handler_cli:
        hid = handler_cli.strip().lower()
        if hid not in _HANDLERS:
            logger.warning("Unknown --handler %r; using generic", handler_cli)
            return GenericComponentHandler(), "generic"
        return _HANDLERS[hid](), hid

    row_h = catalogue_row.get("handler")
    if isinstance(row_h, str) and row_h.strip():
        hid = row_h.strip().lower()
        if hid in _HANDLERS:
            return _HANDLERS[hid](), hid
        logger.warning("Unknown catalogue handler %r; falling through", row_h)

    base_default = (default_handler_id or "hyperui").strip().lower()
    hid = base_default if base_default in _HANDLERS else "hyperui"
    return _HANDLERS[hid](), hid
