from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def resolve_video_provider():
    """Return the configured video provider. Defaults to FakeVideoProvider until a real
    provider (Seedance, AiToEarn) is configured. Never raises — a misconfigured provider must not
    take down the loop; it falls back to fake."""
    from app.config import settings
    from app.video.fake import FakeVideoProvider

    try:
        if settings.video_provider == "aitoearn" and settings.aitoearn_ai_base_url and settings.aitoearn_api_key:
            from app.connectors.aitoearn_client import AiToEarnClient
            from app.video.aitoearn import AiToEarnVideoProvider
            client = AiToEarnClient(settings.aitoearn_base_url or "", settings.aitoearn_api_key,
                                    ai_base_url=settings.aitoearn_ai_base_url)
            return AiToEarnVideoProvider(client, model=settings.aitoearn_video_model)
        if settings.video_provider == "seedance":
            from app.video.seedance import SeedanceVideoProvider

            return SeedanceVideoProvider(
                binary=settings.dreamina_bin,
                model=settings.seedance_model,
                output_dir=settings.video_output_dir,
                public_base_url=settings.public_base_url,
            )
    except Exception as exc:  # noqa: BLE001 - never break the loop on a misconfigured provider
        logger.warning("video provider init failed (%s: %s); falling back to fake", exc.__class__.__name__, exc)

    return FakeVideoProvider()
