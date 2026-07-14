"""Resolve the configured image provider.

Defaults to FakeImageProvider. Never raises — a misconfigured image provider must
not take down the loop; it falls back to fake (mirrors resolve_video_provider)."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def resolve_image_provider():
    from app.config import settings
    from app.image.fake import FakeImageProvider

    try:
        if settings.image_provider == "newapi":
            if settings.anthropic_api_key and settings.anthropic_base_url:
                from app.image.newapi import NewapiImageProvider

                return NewapiImageProvider(
                    base_url=settings.anthropic_base_url,
                    api_key=settings.anthropic_api_key,
                    model=settings.image_model,
                    output_dir=settings.video_output_dir,
                    public_base_url=settings.public_base_url,
                )
            logger.warning(
                "image_provider=newapi but anthropic_base_url/api_key incomplete; "
                "using fake image provider"
            )
        if settings.image_provider == "canvas":
            from app.image.canvas import CanvasImageProvider

            return CanvasImageProvider(
                base_url=settings.canvas_base_url,
                app_token=settings.canvas_app_token,
                model_provider=settings.canvas_image_provider,
                output_dir=settings.video_output_dir,
                public_base_url=settings.public_base_url,
            )
    except Exception as exc:  # noqa: BLE001 - never break the loop on a bad provider
        logger.warning(
            "image provider init failed (%s: %s); falling back to fake",
            exc.__class__.__name__,
            exc,
        )

    return FakeImageProvider(
        output_dir=settings.video_output_dir,
        public_base_url=settings.public_base_url,
    )
