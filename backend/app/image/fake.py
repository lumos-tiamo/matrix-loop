from __future__ import annotations

import base64
import os
import uuid

from app.image.base import ImageResult

# 1x1 transparent PNG — deterministic placeholder so downstream file handling works
# without any network / API key (default provider, and handy in tests).
_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


class FakeImageProvider:
    """Zero-dependency image provider. Writes a placeholder PNG. Used as the safe
    default and when a real provider is misconfigured — never breaks the loop."""

    name = "fake"

    def __init__(self, output_dir: str = "./data/videos", public_base_url: str = ""):
        self.output_dir = output_dir
        self.public_base_url = (public_base_url or "").rstrip("/")

    def generate(
        self, *, prompt: str, refs: list[str] | None = None, params: dict | None = None
    ) -> ImageResult:
        params = params or {}
        os.makedirs(self.output_dir, exist_ok=True)
        fname = params.get("filename") or f"img_fake_{uuid.uuid4().hex[:12]}.png"
        path = os.path.join(self.output_dir, fname)
        with open(path, "wb") as fh:
            fh.write(_PLACEHOLDER_PNG)
        media_url = f"{self.public_base_url}/videos/{fname}" if self.public_base_url else path
        return ImageResult(
            path=path,
            media_url=media_url,
            mime="image/png",
            provider=self.name,
            prompt=prompt,
            metadata={"placeholder": True, "refs": len(refs or [])},
        )
