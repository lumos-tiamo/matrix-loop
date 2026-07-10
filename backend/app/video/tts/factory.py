from __future__ import annotations

import logging
import shutil

logger = logging.getLogger(__name__)


def resolve_tts_provider(settings=None, *, run=None, http_post=None):
    """Return a TTS provider per settings. Order for 'auto': openai (if model+key) -> say
    (if binary present) -> fake. Explicit choices fall back to fake if unavailable.
    Never raises — a misconfigured TTS provider must not break video generation."""
    from app.video.tts.fake import FakeTTSProvider

    if settings is None:
        from app.config import settings as global_settings
        settings = global_settings

    choice = (getattr(settings, "tts_provider", "auto") or "auto").lower()
    out_dir = getattr(settings, "video_output_dir", "./data/videos")

    def _openai():
        base = getattr(settings, "tts_base_url", None) or getattr(settings, "anthropic_base_url", None)
        key = getattr(settings, "tts_api_key", None) or getattr(settings, "anthropic_api_key", None)
        model = getattr(settings, "tts_model", "") or ""
        if not (base and key and model):
            return None
        from app.video.tts.openai import OpenAITTSProvider
        return OpenAITTSProvider(
            base_url=base, api_key=key, model=model,
            voice=getattr(settings, "tts_voice", "alloy"),
            output_dir=out_dir, http_post=http_post, run=run,
        )

    def _say():
        if shutil.which("say") is None:
            return None
        from app.video.tts.say import SayTTSProvider
        return SayTTSProvider(output_dir=out_dir, run=run)  # system default voice

    try:
        if choice == "openai":
            return _openai() or FakeTTSProvider(output_dir=out_dir)
        if choice == "say":
            return _say() or FakeTTSProvider(output_dir=out_dir)
        if choice == "fake":
            return FakeTTSProvider(output_dir=out_dir)
        # auto
        return _openai() or _say() or FakeTTSProvider(output_dir=out_dir)
    except Exception as exc:  # noqa: BLE001 - never break video-gen on a misconfigured TTS
        logger.warning("tts provider init failed (%s: %s); falling back to fake",
                       exc.__class__.__name__, exc)
        return FakeTTSProvider(output_dir=out_dir)
