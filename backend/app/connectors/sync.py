from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.connectors.base import ManualOnlyError
from app.connectors.registry import resolve_connector
from app.models import ContentItem, Snapshot


def sync_account(session: Session, account, *, connector=None, cfg=None) -> dict:
    if connector is None:
        connector, _tier = resolve_connector(account.platform, cfg)
        if connector is None:
            raise ManualOnlyError(f"{account.platform} 无自动连接器，请用 CSV 导入")

    result = connector.fetch(account)
    now = datetime.now(timezone.utc)
    snaps = content = 0
    try:
        for s in result.snapshots:
            session.add(Snapshot(account_id=account.id, ts=now, source_tier=result.tier, **s))
            snaps += 1
        for c in result.content:
            session.add(ContentItem(account_id=account.id, **c))
            content += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    return {"snapshots_created": snaps, "content_created": content, "tier": result.tier}
