from datetime import datetime, timezone

import app.scheduler.batch as batch_mod
from app.models import Account, Snapshot
from app.connectors.base import ConnectorResult
from app.scheduler.batch import run_batch


def _acct(session, platform, handle):
    acc = Account(platform=platform, handle=handle, objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=1000),
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=1100),
    ])
    session.commit()
    return acc


def test_batch_syncs_auto_and_skips_manual(session, monkeypatch):
    _acct(session, "twitter", "@auto")      # has auto connector
    _acct(session, "xiaohongshu", "@manual")  # manual -> skipped, no error

    class FakeConnector:
        tier = "api"
        def fetch(self, account):
            return ConnectorResult(tier="api", snapshots=[{"followers": 2000}], content=[])

    def fake_resolve(platform, cfg=None):
        return (FakeConnector(), "api") if platform == "twitter" else (None, "manual")

    monkeypatch.setattr(batch_mod, "resolve_connector", fake_resolve)
    report = run_batch(session, sync=True)

    assert report.processed == 2
    assert report.looped == 2         # both still loop
    assert report.synced == 1         # only the twitter account synced
    assert report.errors == []        # manual skip is not an error


def test_batch_sync_error_is_nonfatal(session, monkeypatch):
    _acct(session, "twitter", "@auto")

    class BrokenConnector:
        tier = "api"
        def fetch(self, account):
            raise RuntimeError("api down")

    monkeypatch.setattr(batch_mod, "resolve_connector", lambda platform, cfg=None: (BrokenConnector(), "api"))
    report = run_batch(session, sync=True)

    assert report.processed == 1
    assert report.looped == 1                          # loop still runs on existing data
    assert any(e["stage"] == "sync" for e in report.errors)  # sync error recorded, non-fatal
