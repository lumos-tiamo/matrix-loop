from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class VideoResult:
    media_url: str
    duration: float
    cost: float
    provider: str
    dedup_key: str
    metadata: dict = field(default_factory=dict)


class VideoProvider(Protocol):
    name: str
    def generate(self, *, script: str, brief, params: dict) -> VideoResult: ...


class VideoQuotaExceeded(RuntimeError):
    """Raised when a per-day/per-account/per-vertical video quota is hit (a governed stop)."""


class NearDuplicateScript(RuntimeError):
    """Raised when a script is too similar to another account's recent script (differentiation guard)."""
