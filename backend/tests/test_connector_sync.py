import pytest

from app.models import Account, Snapshot, ContentItem
from app.connectors.base import ConnectorResult, ManualOnlyError
from app.connectors.sync import sync_account


class FakeConnector:
    tier = "api"
    def fetch(self, account):
        return ConnectorResult(
            tier="api",
            snapshots=[{"followers": 1234, "engagement_rate": 0.04}],
            content=[{"platform_post_id": "p1", "topic": "beauty", "views": 500}],
        )


def test_sync_persists_snapshot_and_content_with_tier(session):
    acc = Account(platform="twitter", handle="@a")
    session.add(acc)
    session.commit()

    result = sync_account(session, acc, connector=FakeConnector())
    assert result == {"snapshots_created": 1, "content_created": 1, "tier": "api"}

    snap = session.query(Snapshot).filter_by(account_id=acc.id).one()
    assert snap.followers == 1234
    assert snap.source_tier == "api"
    assert session.query(ContentItem).filter_by(account_id=acc.id).one().topic == "beauty"


def test_sync_manual_platform_raises(session):
    acc = Account(platform="xiaohongshu", handle="@x")
    session.add(acc)
    session.commit()
    with pytest.raises(ManualOnlyError):
        sync_account(session, acc)  # no connector, resolves to manual
