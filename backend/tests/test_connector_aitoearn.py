import pytest

from app.connectors.aitoearn import AiToEarnConnector
from app.connectors.base import ManualOnlyError


class _FakeClient:
    def __init__(self, payload): self._payload = payload
    def account_analytics(self, account_id, since=None, until=None): return self._payload


def _acct(external_ref):
    return type("A", (), {"handle": "@x", "platform": "xiaohongshu", "external_ref": external_ref})()


def test_fetch_maps_account_analytics_to_snapshot():
    client = _FakeClient({"metrics": {"fansCount": 5000, "viewCount": 2000, "engagementCount": 100}})
    conn = AiToEarnConnector(client, "xiaohongshu")
    res = conn.fetch(_acct("ae_1"))
    assert res.tier == "aggregator"
    assert res.snapshots == [{"followers": 5000, "views": 2000, "engagement_rate": 0.05}]


def test_fetch_without_external_ref_raises_manual():
    conn = AiToEarnConnector(_FakeClient({}), "douyin")
    with pytest.raises(ManualOnlyError):
        conn.fetch(_acct(None))


def test_fetch_missing_metrics_yields_empty_snapshots():
    conn = AiToEarnConnector(_FakeClient({"metrics": {}}), "tiktok")
    assert conn.fetch(_acct("ae_2")).snapshots == []


def test_sync_persists_aggregator_snapshot(session):
    from app.models import Account, Snapshot
    from app.connectors.sync import sync_account
    acc = Account(platform="xiaohongshu", handle="@x", external_ref="ae_9")
    session.add(acc); session.commit()
    client = _FakeClient({"metrics": {"fansCount": 8000, "viewCount": 4000, "engagementCount": 200}})
    out = sync_account(session, acc, connector=AiToEarnConnector(client, "xiaohongshu"))
    assert out["tier"] == "aggregator" and out["snapshots_created"] == 1
    snap = session.query(Snapshot).filter_by(account_id=acc.id).one()
    assert snap.followers == 8000 and snap.source_tier == "aggregator" and snap.engagement_rate == 0.05
