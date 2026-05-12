"""Tailwind colour utility → inline style via BeautifulSoup (per-token logic, not whole-attribute regex)."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from tools.handlers.base import ComponentHandler


def _merge_style(el: Any, updates: dict[str, str]) -> None:
    existing = el.get("style") or ""
    parts = [p.strip() for p in existing.split(";") if p.strip()]
    keys_seen = {p.split(":")[0].strip().lower() for p in parts if ":" in p}
    for key, val in updates.items():
        klow = key.strip().lower()
        if klow in keys_seen:
            parts = [p for p in parts if not p.lower().startswith(klow + ":")]
        parts.append(f"{key.strip()}: {val}")
    el["style"] = "; ".join(parts)


def apply_tailwind_colour_mapping(html: str, handler: "ComponentHandler") -> tuple[str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    replacements: list[str] = []

    for el in soup.find_all(True):
        classes = el.get("class")
        if not classes:
            continue
        if isinstance(classes, str):
            tokens = classes.split()
        else:
            tokens = list(classes)
        new_tokens: list[str] = []
        style_updates: dict[str, str] = {}
        for token in tokens:
            mapped = handler.map_colour_class(token, el)
            if mapped is None:
                new_tokens.append(token)
                continue
            props, _ = mapped
            replacements.append(f"{token} → {props}")
            for sk, sv in props.items():
                if sk == "color":
                    style_updates["color"] = sv
                elif sk == "background":
                    style_updates["background"] = sv
                elif sk == "border-color":
                    style_updates["border-color"] = sv
        if style_updates:
            _merge_style(el, style_updates)
        if new_tokens:
            el["class"] = new_tokens
        else:
            if "class" in el.attrs:
                del el["class"]

    return str(soup), replacements
