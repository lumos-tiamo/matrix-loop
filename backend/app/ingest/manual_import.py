from __future__ import annotations

import csv
from datetime import datetime
from typing import TextIO

from sqlalchemy.orm import Session

from app.models import Account, Snapshot

_INT_FIELDS = ("followers", "views", "conversions")
_FLOAT_FIELDS = ("engagement_rate", "hit_rate")


def _parse_int(value: str | None) -> int | None:
    value = (value or "").strip()
    return int(value) if value else None


def _parse_float(value: str | None) -> float | None:
    value = (value or "").strip()
    return float(value) if value else None


def import_snapshots_csv(session: Session, fp: TextIO) -> dict:
    """Import account snapshots from a CSV file object. Returns counts.

    Fix #3: the entire import is atomic — any error rolls back so no orphan
    accounts are left behind.  Snapshots are attached via the ORM relationship
    so we never need a per-row flush to obtain account.id.
    """
    reader = csv.DictReader(fp)
    accounts_created = 0
    snapshots_created = 0
    cache: dict[tuple[str, str], Account] = {}

    try:
        for row in reader:
            platform = row["platform"].strip()
            handle = row["handle"].strip()
            key = (platform, handle)

            account = cache.get(key)
            if account is None:
                account = session.query(Account).filter_by(platform=platform, handle=handle).one_or_none()
                if account is None:
                    account = Account(platform=platform, handle=handle)
                    session.add(account)
                    accounts_created += 1
                cache[key] = account

            snapshot = Snapshot(
                ts=datetime.fromisoformat(row["ts"].strip()),
                source_tier="manual",
                **{f: _parse_int(row.get(f)) for f in _INT_FIELDS},
                **{f: _parse_float(row.get(f)) for f in _FLOAT_FIELDS},
            )
            # Attach via relationship — no flush needed to get account.id
            account.snapshots.append(snapshot)
            snapshots_created += 1

        session.commit()
    except Exception:
        session.rollback()
        raise

    return {"accounts_created": accounts_created, "snapshots_created": snapshots_created}
