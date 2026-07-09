from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def resolve_video_provider():
    """Return the configured video provider. Defaults to FakeVideoProvider until a real
    provider (Seedance) is configured. Never raises — a misconfigured provider must not
    take down the loop; it falls back to fake."""
    from app.config import settings
    from app.video.fake import FakeVideoProvider

    if settings.video_provider == "seedance":
        try:
            from app.video.seedance import SeedanceVideoProvider

            return SeedanceVideoProvider(
                binary=settings.dreamina_bin,
                model=settings.seedance_model,
                output_dir=settings.video_output_dir,
                public_base_url=settings.public_base_url,
            )
        except Exception as exc:
            logger.warning(
                "SeedanceVideoProvider init failed (%s: %s); falling back to fake",
                exc.__class__.__name__,
                exc,
            )
            return FakeVideoProvider()

    return FakeVideoProvider()
