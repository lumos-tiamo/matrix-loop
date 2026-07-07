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
    assert result == {"snapshots_created": 1, "content_created": 1, "tier": "api", "endpoint_matched": None}

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


def test_sync_auto_matches_endpoint_from_bio_url(session):
    from app.models import Account, Endpoint
    from app.connectors.base import ConnectorResult
    from app.connectors.sync import sync_account

    class _Fake:
        tier = "api"
        def fetch(self, account):
            return ConnectorResult(tier="api", snapshots=[{"followers": 100}],
                                   bio_url="https://linktr.ee/nina?ref=x")

    ep = Endpoint(name="Nina", url_pattern="linktr.ee/nina")
    acc = Account(platform="twitter", handle="@x",
                  objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add_all([ep, acc]); session.commit()

    out = sync_account(session, acc, connector=_Fake())
    session.refresh(acc)
    assert acc.endpoint_id == ep.id
    assert out.get("endpoint_matched") == "Nina"


def test_sync_does_not_override_existing_endpoint(session):
    from app.models import Account, Endpoint
    from app.connectors.base import ConnectorResult
    from app.connectors.sync import sync_account

    class _Fake:
        tier = "api"
        def fetch(self, account):
            return ConnectorResult(tier="api", snapshots=[], bio_url="https://linktr.ee/nina")

    a = Endpoint(name="A", url_pattern="a.com"); b = Endpoint(name="B", url_pattern="linktr.ee/nina")
    acc = Account(platform="twitter", handle="@y",
                  objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add_all([a, b, acc]); session.commit()
    acc.endpoint_id = a.id; session.commit()

    out = sync_account(session, acc, connector=_Fake())
    session.refresh(acc)
    assert acc.endpoint_id == a.id            # prior wiring preserved
    assert out.get("endpoint_matched") is None


def test_sync_no_bio_url_is_noop_for_endpoint(session):
    from app.models import Account
    from app.connectors.base import ConnectorResult
    from app.connectors.sync import sync_account

    class _Fake:
        tier = "api"
        def fetch(self, account):
            return ConnectorResult(tier="api", snapshots=[{"followers": 5}])

    acc = Account(platform="twitter", handle="@z",
                  objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc); session.commit()
    out = sync_account(session, acc, connector=_Fake())
    session.refresh(acc)
    assert acc.endpoint_id is None
    assert out.get("endpoint_matched") is None


def test_x_connector_extracts_bio_url_from_entities():
    from app.connectors.x import XConnector
    payload = {"data": {"public_metrics": {"followers_count": 1234},
                        "entities": {"url": {"urls": [{"expanded_url": "https://linktr.ee/nina"}]}}}}
    conn = XConnector("tok", http_get=lambda url, headers: payload)
    res = conn.fetch(type("A", (), {"handle": "@nina"})())
    assert res.snapshots == [{"followers": 1234}]
    assert res.bio_url == "https://linktr.ee/nina"
