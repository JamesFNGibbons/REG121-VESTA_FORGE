"""
HyperUI-oriented preprocessing (MIT).

Forge entrypoint is inherited :meth:`~tools.handlers.generic.GenericComponentHandler.preprocess`
(standard pipeline). HyperUI-specific behaviour is confined to :meth:`colour_map` /
:meth:`map_colour_class` and inherited strip/remove hooks from generic.
"""

from __future__ import annotations

import re
from typing import Any

from tools.handlers.generic import GenericComponentHandler


class HyperUIComponentHandler(GenericComponentHandler):
    HANDLER_ID = "hyperui"
    DISPLAY_NAME = "HyperUI"
    DESCRIPTION = "HyperUI full-doc patterns, indigo → brand tokens, Alpine preserved."
    LICENSE_NOTE = "MIT — HyperUI"
    DEFAULT_PALETTE_LABEL = "indigo"

    def colour_map(self) -> dict[str, str]:
        return {
            "primary": "var(--brand-primary)",
            "primary_foreground": "var(--brand-primary-foreground)",
            "border": "var(--brand-primary)",
        }

    def map_colour_class(self, token: str, element: Any = None) -> tuple[dict[str, str], list[str]] | None:
        cmap = self.colour_map()
        if token == "text-white" and element is not None:
            if element.name in ("a", "button", "span"):
                cls = element.get("class") or []
                cjoined = " ".join(cls) if isinstance(cls, list) else str(cls)
                if "bg-" in cjoined or element.name == "button":
                    return ({"color": cmap["primary_foreground"]}, [])
        m = re.match(r"^(text|bg|border)-indigo-(\d{2,3})$", token)
        if not m:
            return super().map_colour_class(token, element)
        prefix, shade_s = m.group(1), m.group(2)
        try:
            shade = int(shade_s)
        except ValueError:
            return None
        if not (400 <= shade <= 900):
            return None
        if prefix == "text":
            return ({"color": cmap["primary"]}, [])
        if prefix == "bg":
            return ({"background": cmap["primary"]}, [])
        if prefix == "border":
            return ({"border-color": cmap["border"]}, [])
        return None
