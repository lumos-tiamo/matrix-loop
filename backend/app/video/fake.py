from __future__ import annotations

import hashlib

from app.video.base import VideoResult


class FakeVideoProvider:
    """Deterministic stand-in until a real provider (Seedance) is wired. Cost is 1.0 'credit'."""

    name = "fake"

    def generate(self, *, script: str, brief, params: dict) -> VideoResult:
        digest = hashlib.sha256((script or "").encode("utf-8")).hexdigest()[:16]
        return VideoResult(
            media_url=f"https://fake.local/video/{digest}.mp4",
            duration=45.0,
            cost=1.0,
            provider=self.name,
            dedup_key=digest,
        )
