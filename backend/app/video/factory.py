from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _resolve_clip_provider(settings, name):
    """Resolve a *clip* provider (aitoearn|seedance|fake) for direct use or as the
    faceless b-roll. Never returns a FacelessVideoProvider — prevents recursion."""
    from app.video.fake import FakeVideoProvider

    if name == "aitoearn" and settings.aitoearn_ai_base_url and settings.aitoearn_api_key:
        from app.connectors.aitoearn_client import AiToEarnClient
        from app.video.aitoearn import AiToEarnVideoProvider
        client = AiToEarnClient(settings.aitoearn_base_url or "", settings.aitoearn_api_key,
                                ai_base_url=settings.aitoearn_ai_base_url)
        return AiToEarnVideoProvider(client, model=settings.aitoearn_video_model)
    if name == "seedance":
        from app.video.seedance import SeedanceVideoProvider
        return SeedanceVideoProvider(
            binary=settings.dreamina_bin,
            model=settings.seedance_model,
            output_dir=settings.video_output_dir,
            public_base_url=settings.public_base_url,
        )
    return FakeVideoProvider()


def resolve_video_provider():
    """Return the configured video provider. Defaults to FakeVideoProvider. Never raises —
    a misconfigured provider must not take down the loop; it falls back to fake."""
    from app.config import settings
    from app.video.fake import FakeVideoProvider

    try:
        if settings.video_provider == "faceless":
            from app.video.faceless import FacelessVideoProvider
            from app.video.tts.factory import resolve_tts_provider
            tts = resolve_tts_provider(settings)
            visual = _resolve_clip_provider(settings, settings.faceless_visual)
            return FacelessVideoProvider(
                tts=tts, visual=visual,
                output_dir=settings.video_output_dir,
                public_base_url=settings.public_base_url,
            )
        if settings.video_provider in ("aitoearn", "seedance"):
            return _resolve_clip_provider(settings, settings.video_provider)
    except Exception as exc:  # noqa: BLE001 - never break the loop on a misconfigured provider
        logger.warning("video provider init failed (%s: %s); falling back to fake",
                       exc.__class__.__name__, exc)

    return FakeVideoProvider()
