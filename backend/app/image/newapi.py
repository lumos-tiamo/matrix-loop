from __future__ import annotations

import base64
import logging
import os
import re
import uuid

from app.image.base import ImageResult

logger = logging.getLogger(__name__)

# newapi / Gemini / Nano-Banana image models return the image inline in the chat
# message as a data: URI, e.g.  ![image](data:image/jpeg;base64,....)
_DATA_URI = re.compile(
    r"data:image/(?P<ext>[a-zA-Z0-9.+-]+);base64,(?P<b64>[A-Za-z0-9+/=\s]+)"
)


class NewapiImageProvider:
    """Image generation via a new-api / OpenAI-compatible gateway using Gemini /
    Nano-Banana image models.

    These models are *conversational* image models: the request goes to
    ``/v1/chat/completions`` and the PNG/JPEG comes back inline as a base64 data URI
    in the assistant message. We decode it and persist to ``output_dir``.

    ``http_post`` is injectable so tests never hit the network (mirrors the
    AiToEarnClient / ClaudeClient convention in this repo).
    """

    name = "newapi"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        output_dir: str,
        public_base_url: str = "",
        http_post=None,
        timeout: float = 120.0,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.model = model
        self.output_dir = output_dir
        self.public_base_url = (public_base_url or "").rstrip("/")
        self._http_post = http_post or self._default_post
        self.timeout = timeout

    def _default_post(self, url: str, headers: dict, json: dict) -> dict:
        import httpx

        resp = httpx.post(url, headers=headers, json=json, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _content(prompt: str, refs: list[str] | None):
        """Build the chat message content. With refs, use the multimodal array form so
        the image model keeps the referenced character/style consistent."""
        if not refs:
            return prompt
        parts: list[dict] = [{"type": "text", "text": prompt}]
        for r in refs:
            parts.append({"type": "image_url", "image_url": {"url": r}})
        return parts

    def generate(
        self, *, prompt: str, refs: list[str] | None = None, params: dict | None = None
    ) -> ImageResult:
        params = params or {}
        model = params.get("model") or self.model
        body = {
            "model": model,
            "messages": [{"role": "user", "content": self._content(prompt, refs)}],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = self._http_post(f"{self.base_url}/v1/chat/completions", headers, body)

        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        if isinstance(content, list):  # some gateways return a content-parts array
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict)
            )
        m = _DATA_URI.search(content or "")
        if not m:
            raise RuntimeError(
                f"newapi image: no image data URI in response "
                f"(model={model!r}): {str(content)[:200]!r}"
            )
        ext = m.group("ext").lower()
        ext = {"jpeg": "jpg"}.get(ext, ext)
        raw = base64.b64decode(re.sub(r"\s+", "", m.group("b64")))

        os.makedirs(self.output_dir, exist_ok=True)
        fname = params.get("filename") or f"img_{uuid.uuid4().hex[:12]}.{ext}"
        path = os.path.join(self.output_dir, fname)
        with open(path, "wb") as fh:
            fh.write(raw)

        media_url = f"{self.public_base_url}/videos/{fname}" if self.public_base_url else path
        return ImageResult(
            path=path,
            media_url=media_url,
            mime=f"image/{ext}",
            provider=self.name,
            prompt=prompt,
            cost=0.0,
            metadata={"model": model, "usage": data.get("usage") or {}, "bytes": len(raw)},
        )
