from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.aitoearn_client import to_aitoearn_platform
from app.models import Account, ContentItem, Draft, PublishDispatch, VideoAsset

logger = logging.getLogger(__name__)


def _parse_dt(value):
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def refresh_published_analytics(session: Session, *, client) -> dict:
    """For every dispatch that has a platform_work_id, pull the post's real analytics and
    upsert an attributed ContentItem (by account_id + platform_post_id). Idempotent."""
    dispatches = session.scalars(
        select(PublishDispatch).where(PublishDispatch.platform_work_id.is_not(None))
    ).all()
    refreshed = 0
    errors: list[dict] = []
    for d in dispatches:
        acc = session.get(Account, d.account_id)
        if acc is None:
            continue
        try:
            data = client.work_analytics(
                to_aitoearn_platform(acc.platform), d.platform_work_id, acc.external_ref or ""
            ) or {}
        except Exception as exc:  # noqa: BLE001 - isolate per-dispatch upstream errors
            logger.warning("work_analytics failed for dispatch %s: %s", d.id, exc)
            errors.append({"dispatch_id": d.id, "error": str(exc)})
            continue

        metrics = data.get("metrics") or {}
        work = data.get("work") or {}

        # attribution: prefer the dispatch's draft; else the video asset's script draft
        draft_id = d.draft_id
        if draft_id is None and d.video_asset_id is not None:
            va = session.get(VideoAsset, d.video_asset_id)
            draft_id = va.script_draft_id if va else None

        ci = session.scalar(
            select(ContentItem).where(
                ContentItem.account_id == acc.id,
                ContentItem.platform_post_id == d.platform_work_id,
            )
        )
        if ci is None:
            ci = ContentItem(account_id=acc.id, platform_post_id=d.platform_work_id)
            session.add(ci)

        views = metrics.get("viewCount")
        if views is None:
            views = metrics.get("playCount")
        if views is not None:
            ci.views = views
        if metrics.get("likeCount") is not None:
            ci.likes = metrics.get("likeCount")
        if metrics.get("commentCount") is not None:
            ci.comments = metrics.get("commentCount")
        ci.type = "video"
        ci.video_asset_id = d.video_asset_id
        ci.draft_id = draft_id
        published_at = _parse_dt(work.get("publishedAt"))
        if published_at is not None:
            ci.published_at = published_at
        if not ci.topic and draft_id is not None:
            dr = session.get(Draft, draft_id)
            if dr and dr.content:
                ci.topic = dr.content[:80]
        refreshed += 1

    session.commit()
    return {"refreshed": refreshed, "errors": errors, "dispatches": len(dispatches)}
