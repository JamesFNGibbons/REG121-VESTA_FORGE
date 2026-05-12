"""Placeholder replacement using BeautifulSoup."""

from __future__ import annotations

import re
from bs4 import BeautifulSoup

_CTA_TEXTS = frozenset(
    {
        "download",
        "get started",
        "learn more",
        "sign up",
        "contact us",
        "book now",
        "submit",
    }
)

_BOILERPLATE_HEADINGS = frozenset({"lorem ipsum", "heading", "your headline", "section title"})

_BOILERPLATE_BODY = frozenset({"lorem ipsum dolor sit amet", "add your content here", "description goes here"})


def _looks_real_content(text: str) -> bool:
    t = text.strip()
    if len(t) < 3:
        return False
    if len(t) > 120:
        return True
    return len(t.split()) > 12


def apply_placeholders(html: str) -> tuple[str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    added: list[str] = []

    for a in soup.find_all("a"):
        href = a.get("href")
        if href in ("#", "", None):
            a["href"] = "[[CTA_PRIMARY_HREF]]"
            added.append("[[CTA_PRIMARY_HREF]]")
        text = a.get_text(strip=True)
        if text and text.lower() in _CTA_TEXTS and not _looks_real_content(text):
            for child in list(a.children):
                if getattr(child, "extract", None):
                    child.extract()
            a.append("[[CTA_PRIMARY_TEXT]]")
            added.append("[[CTA_PRIMARY_TEXT]]")

    for btn in soup.find_all("button"):
        text = btn.get_text(strip=True)
        if text and text.lower() in _CTA_TEXTS and not _looks_real_content(text):
            btn.clear()
            btn.append("[[CTA_PRIMARY_TEXT]]")
            added.append("[[CTA_PRIMARY_TEXT]]")

    for img in soup.find_all("img"):
        if img.get("src"):
            img["src"] = "[[IMAGE_URL]]"
            added.append("[[IMAGE_URL]]")
        if img.has_attr("alt"):
            img["alt"] = "[[IMAGE_ALT]]"
            added.append("[[IMAGE_ALT]]")

    for hx in soup.find_all(re.compile(r"^h[1-6]$")):
        t = hx.get_text(strip=True)
        if not t or len(t) > 100:
            continue
        if t.lower() in _BOILERPLATE_HEADINGS or (len(t) < 40 and not _looks_real_content(t)):
            hx.clear()
            hx.append("[[HEADLINE]]")
            added.append("[[HEADLINE]]")

    for p in soup.find_all("p"):
        t = p.get_text(strip=True)
        if not t or len(t) > 200:
            continue
        if t.lower() in _BOILERPLATE_BODY or (len(t) < 90 and not _looks_real_content(t)):
            p.clear()
            p.append("[[BODY_TEXT]]")
            added.append("[[BODY_TEXT]]")

    return str(soup), list(dict.fromkeys(added))
