"""Resolve the loop's LLM client from configuration.

Returns a live ClaudeClient when an API key is configured, else None so the loop
degrades to its deterministic positioning path. Never raises on missing/broken
config — a misconfigured LLM must not take down the loop or batch run.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def resolve_llm_client():
    from app.config import settings
    if not settings.anthropic_api_key:
        return None
    try:
        from app.analysis.claude_client import ClaudeClient
        return ClaudeClient()
    except Exception as exc:  # noqa: BLE001 - config/SDK errors must not break the loop
        logger.warning("LLM configured but client init failed; using deterministic path: %s", exc)
        return None
