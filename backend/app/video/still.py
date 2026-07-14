from __future__ import annotations

import logging

from app.video.base import VideoResult

logger = logging.getLogger(__name__)


class StillImageVisual:
    """A *visual* (clip-like) provider that yields a single still image instead of a
    video clip, for FacelessVideoProvider to use as the background (ffmpeg loops it
    for the full narration duration).

    Wraps an ImageProvider: generate() produces one Aurea still (optionally locked to
    a reference image for character consistency) and returns it in a VideoResult-shaped
    object whose ``provider="still"`` and ``media_url`` points at the local image path.
    Faceless recognizes provider=="still" and builds a Ken-Burns-ish looped background.
    """

    name = "still"

    def __init__(self, *, image_provider, default_refs: list[str] | None = None):
        self._img = image_provider
        self._default_refs = default_refs or []

    def generate(self, *, script: str, brief, params: dict) -> VideoResult:
        params = params or {}
        prompt = params.get("image_prompt") or params.get("still_prompt") or (
            "Anime / VTuber-style key visual of the same character, vertical 9:16, "
            "clean cel-shaded, cinematic key light. No on-image text or watermark."
        )
        refs = params.get("image_refs") or self._default_refs or None
        img = self._img.generate(prompt=prompt, refs=refs, params=params)
        return VideoResult(
            media_url=img.path,           # local path; faceless loops it as background
            duration=0.0,                 # duration comes from the TTS track
            cost=float(getattr(img, "cost", 0.0) or 0.0),
            provider="still",
            dedup_key=f"still:{getattr(img, 'path', '')}",
            metadata={"image_provider": getattr(img, "provider", ""),
                      "mime": getattr(img, "mime", ""), "path": img.path},
        )
