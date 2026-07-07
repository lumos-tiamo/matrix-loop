from datetime import datetime, timezone

from app.models import Account, Snapshot, Evaluation, LoopRun


def test_create_account_returns_201_and_item(client):
    resp = client.post("/accounts", json={"platform": "xiaohongshu", "handle": "@a1", "vertical": "beauty"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["platform"] == "xiaohongshu"
    assert body["handle"] == "@a1"
    assert body["latest_composite_score"] is None  # 还没评估


def test_list_accounts_includes_latest_metrics(client, session):
    acc = Account(platform="douyin", handle="@a2")
    session.add(acc)
    session.commit()
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc),
                         followers=12345, source_tier="manual"))
    ev = Evaluation(account_id=acc.id, composite_score=73.0, breakdown={})
    run = LoopRun(account_id=acc.id, status="no_progress")
    run.evaluation = ev
    session.add(run)
    session.commit()

    resp = client.get("/accounts")
    assert resp.status_code == 200
    items = resp.json()
    item = next(i for i in items if i["handle"] == "@a2")
    assert item["latest_followers"] == 12345
    assert item["latest_composite_score"] == 73.0
    assert item["latest_loop_status"] == "no_progress"
    assert item["source_tier"] == "manual"
