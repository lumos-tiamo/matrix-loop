from app.models import Account, VideoAsset


def _asset(session, review="approved", platform="twitter"):
    acc = Account(platform=platform, handle="@ae", external_ref="ae_1")
    session.add(acc); session.commit()
    v = VideoAsset(account_id=acc.id, provider="hyperframes", media_url="https://f/x.mp4",
                   dedup_key="k", status="ready", review_status=review)
    session.add(v); session.commit()
    return acc, v


def test_publish_plan_upsert_and_get(client, session):
    acc, v = _asset(session)
    r = client.put(f"/video-assets/{v.id}/publish-plan", json={
        "caption": "gm ser", "hashtags": ["#airdrop", "#defi"],
        "external_link_slot": "first_reply", "external_link_text": "Nina 👇",
        "posting_time": "SEA 20:00", "status": "ready"})
    assert r.status_code == 200
    body = r.json()
    assert body["caption"] == "gm ser"
    assert body["hashtags"] == ["#airdrop", "#defi"]
    assert body["external_link_slot"] == "first_reply"
    assert body["status"] == "ready"
    assert body["platform"] == "twitter"  # inherited from account

    g = client.get(f"/video-assets/{v.id}/publish-plan")
    assert g.status_code == 200 and g.json()["id"] == body["id"]

    # upsert = update in place, not a duplicate row
    r2 = client.put(f"/video-assets/{v.id}/publish-plan", json={"caption": "updated"})
    assert r2.status_code == 200
    assert r2.json()["id"] == body["id"] and r2.json()["caption"] == "updated"
    assert r2.json()["hashtags"] == []  # cleared on this upsert


def test_publish_plan_404_when_absent(client, session):
    _, v = _asset(session)
    assert client.get(f"/video-assets/{v.id}/publish-plan").status_code == 404


def test_publish_plan_404_for_missing_asset(client, session):
    assert client.put("/video-assets/99999/publish-plan", json={"caption": "x"}).status_code == 404


def test_publish_uses_plan_caption_when_none_given(client, session, monkeypatch):
    acc, v = _asset(session)
    client.put(f"/video-assets/{v.id}/publish-plan",
               json={"caption": "from plan", "hashtags": ["#x"]})
    from app.config import settings
    monkeypatch.setattr(settings, "aitoearn_base_url", "http://x/api/v2", raising=False)
    monkeypatch.setattr(settings, "aitoearn_api_key", "k", raising=False)
    captured = {}

    class _FakeClient:
        def __init__(self, *a, **k): pass
        def publish_flow(self, payload):
            captured["payload"] = payload
            return {"flowId": "f1", "tasks": [{"id": "t1", "status": "WaitingForPublish"}]}

    monkeypatch.setattr("app.api.routes.AiToEarnClient", _FakeClient)
    r = client.post(f"/accounts/{acc.id}/publish", json={"video_asset_id": v.id})
    assert r.status_code == 201
    assert "from plan" in captured["payload"]["content"]["title"]
    assert "#x" in captured["payload"]["content"]["body"]


def test_explicit_caption_overrides_plan(client, session, monkeypatch):
    acc, v = _asset(session)
    client.put(f"/video-assets/{v.id}/publish-plan", json={"caption": "from plan"})
    from app.config import settings
    monkeypatch.setattr(settings, "aitoearn_base_url", "http://x/api/v2", raising=False)
    monkeypatch.setattr(settings, "aitoearn_api_key", "k", raising=False)
    captured = {}

    class _FakeClient:
        def __init__(self, *a, **k): pass
        def publish_flow(self, payload):
            captured["payload"] = payload
            return {"flowId": "f1", "tasks": [{"id": "t1", "status": "WaitingForPublish"}]}

    monkeypatch.setattr("app.api.routes.AiToEarnClient", _FakeClient)
    r = client.post(f"/accounts/{acc.id}/publish",
                    json={"video_asset_id": v.id, "caption": "explicit"})
    assert r.status_code == 201
    assert captured["payload"]["content"]["title"] == "explicit"
