"""Published-track summary — a per-work view across platforms, borrowed from xiaobei's
published-track skill. matrix-loop already stores the pieces (PublishDispatch = 发布记录,
ContentItem = 互动数据, Calibration = 盲预测), so this module joins them into the calibration
复盘 view the loop needs: for each published work, its prediction vs. actual and the T+Nd review
状态. No new table — it reads the existing ones."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Calibration, ContentItem, PublishDispatch, VideoAsset


def _actual(item: ContentItem | None) -> dict | None:
    if item is None or item.views is None:
        return None
    inter = (item.likes or 0) + (item.comments or 0) + (item.saves or 0)
    return {"views": int(item.views), "likes": item.likes or 0, "comments": item.comments or 0,
            "saves": item.saves or 0,
            "engagement_rate": round(inter / item.views, 4) if item.views else 0.0}


def track_summary(session: Session, *, account_id: int | None = None, limit: int = 100) -> dict:
    """Per-work published record + interaction data + prediction error, newest first."""
    stmt = select(PublishDispatch).where(PublishDispatch.status.in_(["queued", "published"]))
    if account_id is not None:
        stmt = stmt.where(PublishDispatch.account_id == account_id)
    dispatches = list(session.scalars(stmt.order_by(PublishDispatch.created_at.desc()).limit(limit)))

    works = []
    platforms: dict[str, int] = {}
    for d in dispatches:
        acc = session.get(Account, d.account_id)
        item = session.scalar(
            select(ContentItem).where(ContentItem.video_asset_id == d.video_asset_id)
            .order_by(ContentItem.published_at.desc().nullslast()).limit(1)
        ) if d.video_asset_id else None
        cal = session.scalar(
            select(Calibration).where(Calibration.video_asset_id == d.video_asset_id)
        ) if d.video_asset_id else None
        plat = acc.platform if acc else "?"
        platforms[plat] = platforms.get(plat, 0) + 1
        works.append({
            "dispatch_id": d.id,
            "account": acc.handle if acc else None,
            "platform": plat,
            "video_asset_id": d.video_asset_id,
            "status": d.status,
            "platform_work_id": d.platform_work_id,
            "caption": d.caption,
            "published_at": d.publish_at.isoformat() if d.publish_at else None,
            "actual": _actual(item),
            "predicted": cal.predicted if cal else None,
            "quality_score": cal.quality_score if cal else None,
            "prediction_error": cal.error if cal else None,
            "calibration_status": cal.status if cal else None,
        })

    reviewed = [w for w in works if w["calibration_status"] == "reviewed" and w["prediction_error"]]
    return {
        "total_published": len(works),
        "platforms": platforms,
        "reviewed": len(reviewed),
        "works": works,
    }
