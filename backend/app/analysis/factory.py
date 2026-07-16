"""Resolve the loop's LLM client from configuration.

Returns a live ClaudeClient when an API key is configured, else None so the loop
degrades to its deterministic positioning path. Never raises on missing/broken
config — a misconfigured LLM must not take down the loop or batch run.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _build_agens(settings):
    """Build the AgensAI primary client per its configured protocol, or None if unconfigured."""
    if not (settings.prefer_agens and settings.agens_api_key and settings.agens_base_url):
        return None
    model = settings.agens_model or settings.llm_model
    try:
        if settings.agens_protocol == "anthropic":
            from app.analysis.claude_client import ClaudeClient
            return ClaudeClient(api_key=settings.agens_api_key,
                                base_url=settings.agens_base_url, model=model)
        from app.analysis.fallback_client import OpenAICompatClient
        return OpenAICompatClient(api_key=settings.agens_api_key,
                                  base_url=settings.agens_base_url, model=model)
    except Exception as exc:  # noqa: BLE001 - a broken primary must not break the loop
        logger.warning("AgensAI client init failed; skipping primary: %s", exc)
        return None


def resolve_llm_client():
    from app.config import settings
    secondary = None
    if settings.anthropic_api_key:
        try:
            from app.analysis.claude_client import ClaudeClient
            secondary = ClaudeClient()
        except Exception as exc:  # noqa: BLE001 - config/SDK errors must not break the loop
            logger.warning("newapi LLM client init failed; using deterministic path: %s", exc)

    primary = _build_agens(settings)
    if primary is not None:
        if secondary is None:
            return primary   # only AgensAI configured
        from app.analysis.fallback_client import FallbackLLMClient
        return FallbackLLMClient(primary, secondary)  # AgensAI first → newapi fallback
    return secondary
