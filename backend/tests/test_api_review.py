from app.models import Account, LoopRun, Recommendation, Draft


def _seed_run(session):
    acc = Account(platform="x", handle="@rv")
    session.add(acc)
    session.commit()
    run = LoopRun(account_id=acc.id, status="ok")
    run.recommendations.append(Recommendation(kind="positioning", content="聚焦"))
    run.drafts.append(Draft(kind="topic", content="选题"))
    session.add(run)
    session.commit()
    return run.recommendations[0].id, run.drafts[0].id


def test_adopt_recommendation(client, session):
    rec_id, _ = _seed_run(session)
    resp = client.post(f"/recommendations/{rec_id}/status", json={"status": "adopted"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "adopted"


def test_reject_draft(client, session):
    _, draft_id = _seed_run(session)
    resp = client.post(f"/drafts/{draft_id}/status", json={"review_status": "rejected"})
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "rejected"


def test_invalid_recommendation_status_422(client, session):
    rec_id, _ = _seed_run(session)
    assert client.post(f"/recommendations/{rec_id}/status", json={"status": "bogus"}).status_code == 422


def test_recommendation_404(client):
    assert client.post("/recommendations/99999/status", json={"status": "adopted"}).status_code == 404


def test_status_missing_field_returns_422(client, session):
    rec_id, _ = _seed_run(session)
    assert client.post(f"/recommendations/{rec_id}/status", json={}).status_code == 422
