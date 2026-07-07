from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.orm import Session

from app.connectors.base import ManualOnlyError
from app.connectors.registry import resolve_connector
from app.models import ContentItem, Endpoint, Snapshot


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

        # Auto-fill the monetization endpoint from the profile bio link, but only when the
        # account has none yet — never override a manual/prior assignment. `endpoints` is a
        # tiny domain table and this runs only for still-unrouted accounts, so the load is
        # self-limiting even on the batch path. match_endpoint is imported locally: it lives
        # in app.flow (a leaf module with no model deps), and a top-level import here would
        # create a connectors->flow import cycle at module load.
        matched_name = None
        if result.bio_url and account.endpoint_id is None:
            from app.flow.match import match_endpoint
            endpoints = session.scalars(select(Endpoint)).all()
            ep = match_endpoint(result.bio_url, endpoints)
            if ep is not None:
                account.endpoint_id = ep.id
                matched_name = ep.name

        session.commit()
    except Exception:
        session.rollback()
        raise

    return {"snapshots_created": snaps, "content_created": content,
            "tier": result.tier, "endpoint_matched": matched_name}
