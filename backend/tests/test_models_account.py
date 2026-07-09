from datetime import datetime, timezone

from app.models import Account, Snapshot


def test_create_account_with_defaults(session):
    acc = Account(platform="xiaohongshu", handle="@a1", vertical="beauty")
    session.add(acc)
    session.commit()
    assert acc.id is not None
    assert acc.objective_weights == {"growth": 0.25, "engagement": 0.25, "commercial": 0.25, "positioning": 0.25}


def test_account_external_ref_defaults_none_and_persists(session):
    from app.models import Account
    a = Account(platform="xiaohongshu", handle="@x")
    session.add(a); session.commit()
    assert a.external_ref is None
    assert a.external_source is None
    a.external_ref = "ae_123"
    a.external_source = "aitoearn"
    session.commit()
    got = session.get(Account, a.id)
    assert got.external_ref == "ae_123"
    assert got.external_source == "aitoearn"


def test_snapshot_linked_to_account(session):
    acc = Account(platform="douyin", handle="@a2")
    session.add(acc)
    session.commit()
    snap = Snapshot(
        account_id=acc.id,
        ts=datetime(2026, 7, 6, tzinfo=timezone.utc),
        followers=1000,
        engagement_rate=0.043,
        source_tier="manual",
    )
    session.add(snap)
    session.commit()
    assert snap.id is not None
    assert acc.snapshots[0].followers == 1000
