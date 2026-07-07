from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.connectors.base import ManualOnlyError
from app.connectors.registry import resolve_connector
from app.models import ContentItem, Snapshot


def _cols(model) -> set[str]:
    return {c.key for c in sa_inspect(model).mapper.column_attrs}


def sync_account(session: Session, account, *, connector=None, cfg=None) -> dict:
    if connector is None:
        connector, _tier = resolve_connector(account.platform, cfg)
        if connector is None:
            raise ManualOnlyError(f"{account.platform} 无自动连接器，请用 CSV 导入")

    result = connector.fetch(account)
    now = datetime.now(timezone.utc)
    snaps = content = 0
    snap_cols = _cols(Snapshot) - {"id", "account_id", "ts", "source_tier"}
    content_cols = _cols(ContentItem) - {"id", "account_id"}
    try:
        for s in result.snapshots:
            fields = {k: v for k, v in s.items() if k in snap_cols}
            session.add(Snapshot(account_id=account.id, ts=now, source_tier=result.tier, **fields))
            snaps += 1
        for c in result.content:
            fields = {k: v for k, v in c.items() if k in content_cols}
            session.add(ContentItem(account_id=account.id, **fields))
            content += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    return {"snapshots_created": snaps, "content_created": content, "tier": result.tier}
