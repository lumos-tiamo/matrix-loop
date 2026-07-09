from app.models import Account, VideoAsset


def _approved(session, external_ref="ae_1", review="approved"):
    acc = Account(platform="tiktok", handle="@x", external_ref=external_ref)
    session.add(acc); session.commit()
    v = VideoAsset(account_id=acc.id, provider="fake", media_url="https://f/x.mp4",
                   dedup_key="k", status="ready", review_status=review)
    session.add(v); session.commit()
    return acc, v


def test_publish_requires_aitoearn_configured(client, session, monkeypatch):
    acc, v = _approved(session)
    from app.config import settings
    monkeypatch.setattr(settings, "aitoearn_base_url", None, raising=False)
    monkeypatch.setattr(settings, "aitoearn_api_key", None, raising=False)
    r = client.post(f"/accounts/{acc.id}/publish", json={"video_asset_id": v.id, "caption": "gm"})
    assert r.status_code == 422


def test_publish_dispatches_approved_asset(client, session, monkeypatch):
    acc, v = _approved(session)
    from app.config import settings
    monkeypatch.setattr(settings, "aitoearn_base_url", "http://x/api/v2", raising=False)
    monkeypatch.setattr(settings, "aitoearn_api_key", "k", raising=False)

    class _FakeClient:
        def __init__(self, *a, **k): pass
        def publish_flow(self, payload):
            return {"flowId": "f1", "tasks": [{"id": "t1", "platform": "tiktok", "status": "WaitingForPublish"}]}
        def flow_status(self, fid):
            return {"tasks": [{"id": "t1", "status": "Published", "platformWorkId": "w9"}]}
    monkeypatch.setattr("app.api.routes.AiToEarnClient", _FakeClient)

    r = client.post(f"/accounts/{acc.id}/publish", json={"video_asset_id": v.id, "caption": "gm"})
    assert r.status_code == 201
    body = r.json()
    assert body["aitoearn_flow_id"] == "f1" and body["status"] == "queued"
    did = body["id"]
    # poll
    r2 = client.get(f"/publish/dispatches/{did}")
    assert r2.status_code == 200
    assert r2.json()["platform_work_id"] == "w9" and r2.json()["status"] == "published"


def test_publish_rejects_unapproved(client, session, monkeypatch):
    acc, v = _approved(session, review="pending")
    from app.config import settings
    monkeypatch.setattr(settings, "aitoearn_base_url", "http://x/api/v2", raising=False)
    monkeypatch.setattr(settings, "aitoearn_api_key", "k", raising=False)
    monkeypatch.setattr("app.api.routes.AiToEarnClient", lambda *a, **k: None)
    r = client.post(f"/accounts/{acc.id}/publish", json={"video_asset_id": v.id})
    assert r.status_code == 422


def test_list_dispatches(client, session, monkeypatch):
    acc, v = _approved(session)
    from app.config import settings
    monkeypatch.setattr(settings, "aitoearn_base_url", "http://x/api/v2", raising=False)
    monkeypatch.setattr(settings, "aitoearn_api_key", "k", raising=False)
    class _FakeClient:
        def __init__(self, *a, **k): pass
        def publish_flow(self, payload): return {"flowId": "f1", "tasks": [{"id": "t1", "status": "WaitingForPublish"}]}
    monkeypatch.setattr("app.api.routes.AiToEarnClient", _FakeClient)
    client.post(f"/accounts/{acc.id}/publish", json={"video_asset_id": v.id})
    rows = client.get(f"/publish/dispatches?account_id={acc.id}").json()
    assert len(rows) == 1 and rows[0]["video_asset_id"] == v.id
