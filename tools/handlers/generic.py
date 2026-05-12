"""Safe fallback handler for unknown MIT libraries."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from tools.handlers.base import ComponentHandler

_PREVIEW_CLASSES = re.compile(
    r"^flex\s+flex-wrap\s+justify-center\s+gap-4\s+p-6$|^flex\s+flex-wrap\s+justify-center\s+gap-4\s+p-6\s"
)


class GenericComponentHandler(ComponentHandler):
    HANDLER_ID = "generic"
    DISPLAY_NAME = "Generic"
    DESCRIPTION = "Best-effort doc strip, multi-hue palette mapping, shared placeholders."
    LICENSE_NOTE = "Depends on source; use MIT-licensed libraries only."
    DEFAULT_PALETTE_LABEL = "indigo/blue/violet/purple (400–700)"

    def colour_map(self) -> dict[str, str]:
        return {
            "primary": "var(--brand-primary)",
            "primary_foreground": "var(--brand-primary-foreground)",
            "border": "var(--brand-primary)",
        }

    def extract_component(self, raw_html: str) -> str:
        text = raw_html.strip()
        if not text.lower().startswith("<!doctype") and "<html" not in text.lower():
            return text
        soup = BeautifulSoup(text, "html.parser")
        body = soup.body
        if body is None:
            return text
        inner = body.decode_contents() if hasattr(body, "decode_contents") else text
        return inner.strip() or text

    def remove_library_artifacts(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("link"):
            href = (tag.get("href") or "").lower()
            if "component.css" in href or href.endswith("/component.css"):
                tag.decompose()
                self._note_artifact("removed link component.css")
        for tag in soup.find_all("script"):
            src = (tag.get("src") or "").lower()
            if "component.js" in src or src.endswith("/component.js"):
                tag.decompose()
                self._note_artifact("removed script component.js")
        for div in soup.find_all("div", class_=True):
            cls = div.get("class")
            if not cls:
                continue
            cstr = " ".join(cls) if isinstance(cls, list) else str(cls)
            if _PREVIEW_CLASSES.match(cstr.strip()) or cstr.strip() == "flex flex-wrap justify-center gap-4 p-6":
                inner = "".join(str(x) for x in div.children)
                div.replace_with(BeautifulSoup(inner, "html.parser"))
                self._note_artifact("stripped preview wrapper div")
                break
        return str(soup)

    def add_placeholders(self, html: str) -> str:
        return html

    def map_colour_class(self, token: str, element: Any = None) -> tuple[dict[str, str], list[str]] | None:
        m = re.match(r"^(text|bg|border)-([a-z]+)-(\d{2,3})$", token)
        if not m:
            if token == "text-white" and element is not None:
                if element.name in ("a", "button", "span"):
                    cmap = self.colour_map()
                    return ({"color": cmap["primary_foreground"]}, [])
            return None
        prefix, color, shade_s = m.groups()
        try:
            shade = int(shade_s)
        except ValueError:
            return None
        if color not in {"indigo", "blue", "violet", "purple"} or not (400 <= shade <= 700):
            return None
        cmap = self.colour_map()
        if prefix == "text":
            return ({"color": cmap["primary"]}, [])
        if prefix == "bg":
            return ({"background": cmap["primary"]}, [])
        if prefix == "border":
            return ({"border-color": cmap["border"]}, [])
        return None
