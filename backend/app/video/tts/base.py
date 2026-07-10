from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class TTSResult:
    audio_path: str
    duration_seconds: float
    fmt: str  # "wav" | "mp3"


class TTSProvider(Protocol):
    name: str

    def synthesize(self, *, text: str, voice: str | None = None) -> TTSResult: ...
