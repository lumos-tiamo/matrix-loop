from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem, LoopRun, Evaluation


def test_overview_still_correct_after_batching(client, session):
    a1 = Account(platform="xiaohongshu", handle="@a1"); a2 = Account(platform="twitter", handle="@a2")
    session.add_all([a1, a2]); session.commit()
    session.add_all([
        Snapshot(account_id=a1.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100000),
        Snapshot(account_id=a1.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=112000),
        Snapshot(account_id=a2.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=49000),
    ])
    r = LoopRun(account_id=a1.id, status="ok")
    r.evaluation = Evaluation(account_id=a1.id, composite_score=88.0, breakdown={"growth": 90, "engagement": 80, "commercial": 60, "positioning": 92})
    session.add(r); session.commit()

    body = client.get("/overview").json()
    assert body["kpis"]["total_accounts"] == 2
    assert body["kpis"]["avg_score"] == 88.0            # only a1 has an eval
    trend = {t["date"]: t["followers"] for t in body["trend"]}
    assert trend["2026-07-06"] == 161000
    movers = {m["account_id"]: m["delta_followers"] for m in body["top_movers"]}
    assert movers[a1.id] == 12000


def test_content_sorted_in_sql(client, session):
    acc = Account(platform="x", handle="@a"); session.add(acc); session.commit()
    session.add_all([
        ContentItem(account_id=acc.id, topic="a", views=100),
        ContentItem(account_id=acc.id, topic="b", views=9000),
        ContentItem(account_id=acc.id, topic="c", views=None),   # null views sort last
    ])
    session.commit()
    items = client.get("/content?limit=2").json()
    assert [i["views"] for i in items] == [9000, 100]     # views desc, limit applied, null excluded from top
