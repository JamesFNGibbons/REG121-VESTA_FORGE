"""OpenAI SDK client for arbitrary OpenAI-compatible roots (no URL rewriting)."""

from __future__ import annotations

from openai import OpenAI


def openai_client_at_base_url(base_url: str, api_key: str) -> OpenAI:
    """Use the given base URL as-is (e.g. DeepInfra `https://api.deepinfra.com/v1/openai`)."""
    return OpenAI(base_url=base_url.rstrip("/"), api_key=api_key or "dummy")
