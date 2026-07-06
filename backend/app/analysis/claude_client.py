from __future__ import annotations

from app.config import settings


class ClaudeClient:
    """Real LLMClient backed by the Anthropic SDK.

    Reads api key / base_url / model from Settings (env prefix MATRIXLOOP_) unless
    overridden. base_url can point at an OpenClaw gateway. Not exercised against the
    live API in tests - the request-building path is covered via a monkeypatched SDK.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = api_key if api_key is not None else settings.anthropic_api_key
        self.base_url = base_url if base_url is not None else settings.anthropic_base_url
        self.model = model or settings.llm_model
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not configured - set MATRIXLOOP_ANTHROPIC_API_KEY "
                "in the environment/.env or pass api_key=..."
            )
        import anthropic

        kwargs: dict = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = anthropic.Anthropic(**kwargs)

    def complete(self, *, system: str, prompt: str) -> str:
        message = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )
