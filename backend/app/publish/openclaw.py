"""Key-free publish adapter via openclaw — borrowed from xiaobei's platform publish skills.

xiaobei publishes to 小红书/抖音/视频号/Twitter/微博/知乎/B站/YouTube by driving a logged-in
browser through openclaw, so it needs no official platform API keys. matrix-loop reuses that:
this adapter POSTs an approved VideoAsset to the user's openclaw gateway, which does the actual
browser publish, and records a PublishDispatch (source="openclaw") — closing the "先不接key"
gap without wiring every platform's official API.

Human-gated like the AiToEarn path: the asset must be approved and the calibration quality門
(if present) must have passed before we publish.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Calibration, PublishDispatch, VideoAsset
from app.publish.dispatch import PublishNotReady

logger = logging.getLogger(__name__)


def _openclaw_post(path: str, payload: dict, timeout: float = 60.0) -> dict:
    from app.config import settings
    base = (settings.openclaw_base_url or "").rstrip("/")
    if not base:
        raise PublishNotReady("openclaw 未配置(MATRIXLOOP_OPENCLAW_BASE_URL 为空)")
    import httpx
    headers = {"Authorization": f"Bearer {settings.openclaw_token}"} if settings.openclaw_token else {}
    resp = httpx.post(f"{base}{path}", json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def publish_via_openclaw(session: Session, account: Account, asset: VideoAsset, *,
                         platform: str | None = None, caption: str | None = None,
                         enforce_gate: bool = True, poster=None) -> PublishDispatch:
    """Publish an APPROVED asset through openclaw and record a PublishDispatch.
    `poster` is an injectable (path, payload)->dict for tests; defaults to the live HTTP call."""
    if asset.review_status != "approved":
        raise PublishNotReady("video asset must be human-approved before publishing")
    if not asset.media_url:
        raise PublishNotReady("video asset has no media_url")

    if enforce_gate:
        cal = session.scalar(select(Calibration).where(Calibration.video_asset_id == asset.id))
        if cal is not None and not cal.gate_passed:
            raise PublishNotReady(
                f"calibration 质量门未通过(quality {cal.quality_score} < 阈值);不发布低质内容")

    existing = session.scalar(
        select(PublishDispatch).where(
            PublishDispatch.video_asset_id == asset.id,
            PublishDispatch.status != "failed",
        )
    )
    if existing is not None:
        raise PublishNotReady(
            f"video asset {asset.id} already dispatched (dispatch #{existing.id}); refusing to double-publish")

    target = platform or account.platform
    payload = {
        "platform": target,
        "handle": account.handle,
        "media_url": asset.media_url,
        "caption": caption or "",
    }
    post = poster or _openclaw_post
    try:
        result = post("/publish", payload)
    except PublishNotReady:
        raise
    except Exception as exc:  # noqa: BLE001 - record the failure, surface to caller
        logger.warning("openclaw publish failed for asset %s: %s", asset.id, exc)
        dispatch = PublishDispatch(
            account_id=account.id, video_asset_id=asset.id, draft_id=asset.script_draft_id,
            status="failed", media_urls=[asset.media_url], caption=caption,
            publish_at=datetime.now(timezone.utc))
        session.add(dispatch)
        session.commit()
        raise

    work_id = result.get("work_id") or result.get("platform_work_id")
    status = result.get("status", "published")
    dispatch = PublishDispatch(
        account_id=account.id, video_asset_id=asset.id, draft_id=asset.script_draft_id,
        platform_work_id=work_id, status=status if status in ("queued", "published", "failed") else "queued",
        media_urls=[asset.media_url], caption=caption, publish_at=datetime.now(timezone.utc))
    session.add(dispatch)
    # mark the calibration published so it enters the T+Nd review queue
    cal = session.scalar(select(Calibration).where(Calibration.video_asset_id == asset.id))
    if cal is not None and cal.status == "predicted":
        cal.status = "published"
    session.commit()
    return dispatch
