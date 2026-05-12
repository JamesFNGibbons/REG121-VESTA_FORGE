"""OpenAI-compatible client pointed at LiteLLM (/v1)."""

from __future__ import annotations

from openai import OpenAI


def openai_client_for_litellm(base_url: str, api_key: str) -> OpenAI:
    root = base_url.rstrip("/")
    if not root.endswith("/v1"):
        root = root + "/v1"
    return OpenAI(base_url=root, api_key=api_key or "dummy")
