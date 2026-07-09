from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def resolve_video_provider():
    """Return the configured video provider. Defaults to FakeVideoProvider until a real
    provider (Seedance) is configured. Never raises — a misconfigured provider must not
    take down the loop; it falls back to fake."""
    from app.video.fake import FakeVideoProvider
    return FakeVideoProvider()
