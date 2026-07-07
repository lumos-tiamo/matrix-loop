from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem, LoopRun, Evaluation, Recommendation, Draft


def test_account_detail_returns_nested(client, session):
    acc = Account(platform="x", handle="@a3")
    session.add(acc)
    session.commit()
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=500))
    session.add(ContentItem(account_id=acc.id, topic="ai", views=999))
    run = LoopRun(account_id=acc.id, diagnosis="诊断", status="ok")
    run.evaluation = Evaluation(account_id=acc.id, composite_score=61.0, breakdown={"growth": 61})
    run.recommendations.append(Recommendation(kind="positioning", content="聚焦"))
    run.drafts.append(Draft(kind="topic", content="选题一"))
    session.add(run)
    session.commit()

    resp = client.get(f"/accounts/{acc.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["handle"] == "@a3"
    assert body["snapshots"][0]["followers"] == 500
    assert body["content_items"][0]["topic"] == "ai"
    assert body["loop_runs"][0]["diagnosis"] == "诊断"
    assert body["loop_runs"][0]["evaluation"]["composite_score"] == 61.0
    assert body["loop_runs"][0]["recommendations"][0]["content"] == "聚焦"
    assert body["loop_runs"][0]["drafts"][0]["content"] == "选题一"


def test_account_detail_404(client):
    assert client.get("/accounts/99999").status_code == 404
