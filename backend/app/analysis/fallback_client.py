"""AgensAI-first LLM client with automatic fallback to newapi.

The user's AgensAI relay has a free daily quota — prefer it, and only when it's exhausted
(quota/rate-limit/auth error) fall through to the paid newapi relay. FallbackLLMClient wraps a
primary + secondary LLMClient and does exactly that, per call, so a mid-day quota reset means we
silently go back to using the free tier on the next call.

AgensAI's wire protocol may be OpenAI-compatible (/chat/completions) or Anthropic-compatible
(/v1/messages) — both are supported (OpenAICompatClient here; ClaudeClient for anthropic).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# substrings that mean "this provider is out of quota / throttled / unauthorized" -> fall back
_FALLBACK_MARKERS = (
    "quota", "insufficient", "balance", "credit", "rate limit", "rate_limit",
    "429", "too many requests", "exhaust", "limit reached", "401", "403",
    "unauthorized", "invalid api key", "payment",
)


def _should_fallback(exc: Exception) -> bool:
    msg = str(exc).lower()
    if any(m in msg for m in _FALLBACK_MARKERS):
        return True
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    return status in (401, 402, 403, 429)


class OpenAICompatClient:
    """Minimal OpenAI-compatible chat client (implements the LLMClient .complete protocol) over
    httpx, so we don't need the openai SDK. Points at any {base_url}/chat/completions relay."""

    def __init__(self, *, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.last_usage: dict | None = None

    def complete(self, *, system: str, prompt: str) -> str:
        import httpx
        # accept base_url given either with or without a trailing /v1
        url = self.base_url + ("" if self.base_url.endswith("/v1") else "/v1") + "/chat/completions"
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "max_tokens": 2048,
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": prompt}]},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage") or {}
        self.last_usage = {"input": usage.get("prompt_tokens", 0) or 0,
                           "output": usage.get("completion_tokens", 0) or 0}
        return data["choices"][0]["message"]["content"] or ""


class FallbackLLMClient:
    """Try `primary` first; on a quota/rate/auth failure, transparently retry on `secondary`.
    Exposes .last_usage from whichever client actually served the call."""

    def __init__(self, primary, secondary, *, primary_name="agens", secondary_name="newapi"):
        self._primary = primary
        self._secondary = secondary
        self._primary_name = primary_name
        self._secondary_name = secondary_name
        self.last_usage: dict | None = None
        self.last_provider: str | None = None

    def complete(self, *, system: str, prompt: str) -> str:
        try:
            out = self._primary.complete(system=system, prompt=prompt)
            self.last_usage = getattr(self._primary, "last_usage", None)
            self.last_provider = self._primary_name
            return out
        except Exception as exc:  # noqa: BLE001 - decide fallback vs re-raise
            if not _should_fallback(exc):
                raise
            logger.info("%s exhausted/unavailable (%s); falling back to %s",
                        self._primary_name, str(exc)[:120], self._secondary_name)
        out = self._secondary.complete(system=system, prompt=prompt)
        self.last_usage = getattr(self._secondary, "last_usage", None)
        self.last_provider = self._secondary_name
        return out
