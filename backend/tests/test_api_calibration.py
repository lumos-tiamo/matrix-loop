from app.models import Account, Draft, LoopRun, VideoAsset


def _seed_asset(session, review_status="approved"):
    acc = Account(platform="x", handle="@apical")
    session.add(acc)
    session.commit()
    run = LoopRun(account_id=acc.id, status="ok")
    run.drafts.append(Draft(kind="script", content="钩子?3招空投,关注主页。\n正文更多。", review_status="adopted"))
    session.add(run)
    session.commit()
    asset = VideoAsset(account_id=acc.id, script_draft_id=run.drafts[0].id, provider="fake",
                       media_url="http://x/v.mp4", status="ready", review_status=review_status)
    session.add(asset)
    session.commit()
    return acc, asset


def test_calibrate_then_get(client, session):
    _, asset = _seed_asset(session)
    r = client.post(f"/video-assets/{asset.id}/calibrate")
    assert r.status_code == 200
    body = r.json()
    assert body["video_asset_id"] == asset.id and "predicted" in body
    r2 = client.get(f"/video-assets/{asset.id}/calibration")
    assert r2.status_code == 200 and r2.json()["id"] == body["id"]


def test_rubric_and_summary_endpoints(client, session):
    assert client.get("/calibration/rubric").json()["version"] == "v1"
    s = client.get("/calibration/summary").json()
    assert "rubric_version" in s and "threshold" in s


def test_review_endpoint(client, session):
    _, asset = _seed_asset(session)
    cal = client.post(f"/video-assets/{asset.id}/calibrate").json()
    r = client.post(f"/calibration/{cal['id']}/review", json={"actual": {"views": 100, "engagement_rate": 0.05}})
    assert r.status_code == 200 and r.json()["status"] == "reviewed"


def test_evolve_requires_reviews_409(client, session):
    assert client.post("/calibration/evolve-rubric").status_code == 409


def test_smart_search_sources_endpoint(client, session):
    assert "openclaw" in client.get("/smart-search/sources").json()["sources"]


def test_publish_track_endpoint(client, session):
    assert client.get("/publish/track").json()["total_published"] == 0


def test_publish_openclaw_not_configured_409(client, session):
    _, asset = _seed_asset(session)
    # no openclaw base -> adapter raises PublishNotReady -> 409
    r = client.post(f"/video-assets/{asset.id}/publish-openclaw", json={"platform": "tiktok"})
    assert r.status_code == 409
