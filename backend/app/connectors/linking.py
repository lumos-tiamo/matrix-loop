from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.aitoearn_client import to_aitoearn_platform
from app.models import Account


def _norm(s: str | None) -> str:
    return (s or "").lstrip("@").strip().lower()


def link_aitoearn_accounts(session: Session, client) -> dict:
    """Match AiToEarn accounts to matrix-loop accounts by (platform, handle~nickname|uid),
    filling external_ref/external_source. Idempotent; only fills empty external_ref."""
    rows = (client.list_accounts() or {}).get("list") or []
    # index AiToEarn rows by (type, normalized nickname) and (type, normalized uid)
    by_key: dict[tuple[str, str], str] = {}
    for r in rows:
        rid, rtype = r.get("id"), r.get("type")
        if not rid or not rtype:
            continue
        for field in ("nickname", "uid"):
            key = (rtype, _norm(r.get(field)))
            if key[1]:
                by_key.setdefault(key, rid)

    accounts = list(session.scalars(select(Account)).all())
    linked = 0
    for acc in accounts:
        if acc.external_ref:
            continue
        ae_type = to_aitoearn_platform(acc.platform)
        rid = by_key.get((ae_type, _norm(acc.handle)))
        if rid:
            acc.external_ref = rid
            acc.external_source = "aitoearn"
            linked += 1
    session.commit()
    unmatched = sum(1 for a in accounts if not a.external_ref)
    return {"linked": linked, "unmatched_accounts": unmatched, "aitoearn_accounts": len(rows)}
