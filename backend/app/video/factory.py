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
    if name == "aitoearn":
        logger.warning("faceless_visual=aitoearn but aitoearn_ai_base_url/api_key incomplete; "
                       "using fake b-roll")
    if name == "seedance":
        from app.video.seedance import SeedanceVideoProvider
        return SeedanceVideoProvider(
            binary=settings.dreamina_bin,
            model=settings.seedance_model,
            output_dir=settings.video_output_dir,
            public_base_url=settings.public_base_url,
        )
    return FakeVideoProvider()


_STORY_SYSTEM = (
    "You turn a short spoken video narration into a brief visual STORY that an AI film tool "
    "can dramatize into scenes. Invent a concrete setting, one or two recurring characters, and "
    "3-6 short vivid scene beats that illustrate the narration's ideas. Prose only, no headings, "
    "no shot lists. Keep it under 250 words. Write in the requested language."
)


def _waoowaoo_story_writer(settings):
    """Return callable(script, brief)->str that rewrites narration into a dramatizable story,
    or None when no LLM key is configured (adapter then feeds the raw script to waoowaoo)."""
    if not settings.anthropic_api_key:
        return None

    def _write(script: str, brief) -> str:
        from app.analysis.claude_client import ClaudeClient

        lang = getattr(brief, "language", None) or settings.waoowaoo_locale or "en"
        direction = getattr(brief, "main_direction", "") or ""
        prompt = (f"Language: {lang}\nChannel theme: {direction}\n\n"
                  f"Narration to illustrate:\n{script}")
        return ClaudeClient().complete(system=_STORY_SYSTEM, prompt=prompt).strip()

    return _write


def _compositor(settings):
    """Final-mux strategy for faceless-based providers: RemotionComposer when configured, else
    None (FacelessVideoProvider falls back to its built-in ffmpeg mux)."""
    if getattr(settings, "faceless_compositor", "ffmpeg") != "remotion":
        return None
    from app.video.remotion_composer import RemotionComposer
    return RemotionComposer(remotion_dir=settings.remotion_dir, node_bin=settings.remotion_node_bin)


def resolve_video_provider():
    """Return the configured video provider. Defaults to FakeVideoProvider. Never raises —
    a misconfigured provider must not take down the loop; it falls back to fake."""
    from app.config import settings
    from app.video.fake import FakeVideoProvider

    try:
        if settings.video_provider == "hyperframes":
            import os
            import sys
            from app.video.hyperframes import HyperframesVideoProvider
            batch = os.path.abspath(os.path.join(os.getcwd(), settings.hyperframes_batch_dir))
            return HyperframesVideoProvider(
                batch_dir=batch,
                python_bin=settings.hyperframes_python or sys.executable,
                output_dir=settings.video_output_dir,
                public_base_url=settings.public_base_url,
                quality=settings.hyperframes_quality,
            )
        if settings.video_provider == "faceless":
            from app.video.faceless import FacelessVideoProvider
            from app.video.tts.factory import resolve_tts_provider
            tts = resolve_tts_provider(settings)
            visual = _resolve_clip_provider(settings, settings.faceless_visual)
            return FacelessVideoProvider(
                tts=tts, visual=visual,
                output_dir=settings.video_output_dir,
                public_base_url=settings.public_base_url,
                compositor=_compositor(settings),
            )
        if settings.video_provider == "avatar":
            # Aurea digital-host: newapi still (Nano-Banana, character-consistent) +
            # edge-tts 繁中 voiceover + burned captions, composed by faceless.
            from app.image.factory import resolve_image_provider
            from app.video.faceless import FacelessVideoProvider
            from app.video.still import StillImageVisual
            from app.video.tts.factory import resolve_tts_provider

            tts = resolve_tts_provider(settings)
            visual = StillImageVisual(image_provider=resolve_image_provider())
            return FacelessVideoProvider(
                tts=tts, visual=visual,
                output_dir=settings.video_output_dir,
                public_base_url=settings.public_base_url,
                compositor=_compositor(settings),
            )
        if settings.video_provider == "waoowaoo_narrated":
            # waoowaoo drama clips (b-roll) + TTS 口播 + burned captions, composed by faceless.
            # The waoowaoo visual degrades to a Nano-Banana still on any pipeline failure so a
            # waoowaoo outage never stalls the loop.
            from app.image.factory import resolve_image_provider
            from app.video.faceless import FacelessVideoProvider
            from app.video.still import StillImageVisual
            from app.video.tts.factory import resolve_tts_provider
            from app.video.waoowaoo_broll import WaoowaooBrollProvider

            tts = resolve_tts_provider(settings)
            fallback = StillImageVisual(image_provider=resolve_image_provider())
            visual = WaoowaooBrollProvider(
                base_url=settings.waoowaoo_base_url,
                internal_token=settings.waoowaoo_internal_token,
                user_id=settings.waoowaoo_user_id,
                sf_api_key=settings.waoowaoo_sf_api_key,
                sf_base_url=settings.waoowaoo_sf_base_url,
                sf_video_model=settings.waoowaoo_sf_video_model,
                panels=settings.waoowaoo_panels,
                locale=settings.waoowaoo_locale,
                output_dir=settings.video_output_dir,
                public_base_url=settings.public_base_url,
                story_writer=_waoowaoo_story_writer(settings),
                fallback_visual=fallback,
            )
            return FacelessVideoProvider(
                tts=tts, visual=visual,
                output_dir=settings.video_output_dir,
                public_base_url=settings.public_base_url,
                compositor=_compositor(settings),
            )
        if settings.video_provider == "runninghub":
            if settings.runninghub_api_key:
                from app.video.runninghub import RunningHubClient, RunningHubVideoProvider
                client = RunningHubClient(
                    api_key=settings.runninghub_api_key,
                    base_url=settings.runninghub_base_url,
                )
                return RunningHubVideoProvider(
                    client=client,
                    model=settings.runninghub_i2v_workflow_id or "wan",
                    output_dir=settings.video_output_dir,
                    public_base_url=settings.public_base_url,
                )
            logger.warning("video_provider=runninghub but runninghub_api_key missing; using fake")
        if settings.video_provider in ("aitoearn", "seedance"):
            return _resolve_clip_provider(settings, settings.video_provider)
    except Exception as exc:  # noqa: BLE001 - never break the loop on a misconfigured provider
        logger.warning("video provider init failed (%s: %s); falling back to fake",
                       exc.__class__.__name__, exc)

    return FakeVideoProvider()


def _avatar_handles() -> set[str]:
    from app.config import settings
    raw = getattr(settings, "avatar_handles", "") or ""
    return {h.strip().lstrip("@").lower() for h in raw.split(",") if h.strip()}


def make_account_provider_resolver():
    """Return a callable ``resolver(account) -> VideoProvider`` for per-account routing:
    accounts whose handle is in settings.avatar_handles get the Aurea digital-host
    (avatar) provider; everyone else gets the global resolve_video_provider().

    Providers are built once and cached, so a whole autopilot cycle reuses them
    instead of re-constructing per account. Pass this to run_autopilot_cycle(video=...).
    """
    from app.config import settings

    handles = _avatar_handles()
    cache: dict[str, object] = {}

    def _avatar_provider():
        if "avatar" not in cache:
            # build the avatar provider by temporarily reading it through the factory
            prev = settings.video_provider
            try:
                settings.video_provider = "avatar"
                cache["avatar"] = resolve_video_provider()
            finally:
                settings.video_provider = prev
        return cache["avatar"]

    def _global_provider():
        if "global" not in cache:
            cache["global"] = resolve_video_provider()
        return cache["global"]

    def resolver(account):
        handle = (getattr(account, "handle", "") or "").lstrip("@").lower()
        if handle in handles:
            return _avatar_provider()
        return _global_provider()

    return resolver
