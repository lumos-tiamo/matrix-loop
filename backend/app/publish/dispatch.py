from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.connectors.aitoearn_client import to_aitoearn_platform
from app.models import PublishDispatch, VideoAsset


class PublishNotReady(RuntimeError):
    """Raised when a video asset cannot be dispatched (not approved / account not mapped)."""


# AiToEarn task status -> our dispatch status
_STATUS_MAP = {
    "WaitingForPublish": "queued",
    "Publishing": "queued",
    "Published": "published",
    "Failed": "failed",
}


def _map_status(task_status: str | None) -> str:
    return _STATUS_MAP.get(task_status or "", "queued")


def create_dispatch(session: Session, account, asset: VideoAsset, *, client,
                    caption: str | None = None, publish_at: datetime | None = None) -> PublishDispatch:
    """Publish an APPROVED video asset via AiToEarn and record a PublishDispatch.
    Human-gated: the asset must already be human-approved; this call is the explicit publish action."""
    if asset.review_status != "approved":
        raise PublishNotReady("video asset must be human-approved before publishing")
    if not account.external_ref:
        raise PublishNotReady(f"account {account.handle} 未映射 AiToEarn accountId(external_ref)")
    if not asset.media_url:
        raise PublishNotReady("video asset has no media_url")

    when = publish_at or datetime.now(timezone.utc)
    payload = {
        "content": {
            "title": caption or "",
            "body": caption or "",
            "media": [{"url": asset.media_url, "options": {}}],
        },
        "publishAt": when.isoformat(),
        "items": [{
            "accountId": account.external_ref,
            "platform": to_aitoearn_platform(account.platform),
        }],
    }
    resp = client.publish_flow(payload) or {}
    tasks = resp.get("tasks") or []
    task = tasks[0] if tasks else {}
    dispatch = PublishDispatch(
        account_id=account.id,
        video_asset_id=asset.id,
        aitoearn_flow_id=resp.get("flowId"),
        aitoearn_task_id=task.get("id"),
        platform_work_id=task.get("platformWorkId"),
        status=_map_status(task.get("status")),
        publish_at=when,
        media_urls=[asset.media_url],
        caption=caption,
    )
    session.add(dispatch)
    session.commit()
    return dispatch


def refresh_dispatch(session: Session, dispatch: PublishDispatch, *, client) -> PublishDispatch:
    """Poll AiToEarn for the flow's current status; update platform_work_id + status."""
    if not dispatch.aitoearn_flow_id:
        return dispatch
    resp = client.flow_status(dispatch.aitoearn_flow_id) or {}
    tasks = resp.get("tasks") or []
    # prefer the task we recorded; else the first
    task = next((t for t in tasks if t.get("id") == dispatch.aitoearn_task_id), tasks[0] if tasks else {})
    if task.get("platformWorkId"):
        dispatch.platform_work_id = task["platformWorkId"]
    dispatch.status = _map_status(task.get("status"))
    session.commit()
    return dispatch
