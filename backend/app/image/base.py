from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ImageResult:
    path: str                       # local file path on disk
    media_url: str                  # public URL (served under public_base_url) or the path
    mime: str                       # e.g. "image/png"
    provider: str
    prompt: str
    cost: float = 0.0
    metadata: dict = field(default_factory=dict)


class ImageProvider(Protocol):
    name: str

    def generate(
        self, *, prompt: str, refs: list[str] | None = None, params: dict | None = None
    ) -> ImageResult:
        """Generate one image.

        refs: optional reference images (data: URIs or http URLs) for character
        consistency (e.g. lock the Aurea look across shots).
        """
        ...
