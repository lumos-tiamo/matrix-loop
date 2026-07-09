from app.models import Account, Draft, LoopRun, VideoAsset, PublishDispatch, FlywheelEvent


def _seed(session):
    a = Account(platform="tiktok", handle="@x"); session.add(a); session.commit()
    return a


def test_autopilot_toggle(client, session):
    a = _seed(session)
    r = client.post(f"/accounts/{a.id}/autopilot", json={"enabled": True})
    assert r.status_code == 200 and r.json()["autopilot"] is True
    session.refresh(a); assert a.autopilot is True


def test_pause_resume_status(client, session):
    assert client.get("/flywheel/status").json()["paused"] is False
    assert client.post("/flywheel/pause").status_code == 200
    assert client.get("/flywheel/status").json()["paused"] is True
    client.post("/flywheel/resume")
    assert client.get("/flywheel/status").json()["paused"] is False


def test_flywheel_state_shape(client, session):
    a = _seed(session); a.autopilot = True; session.commit()
    session.add(FlywheelEvent(account_id=a.id, step="script", status="ok", detail="x")); session.commit()
    body = client.get("/flywheel").json()
    assert "steps" in body and len(body["steps"]) == 9         # the 9 flywheel steps
    assert "accounts" in body and "events" in body and "paused" in body
    assert any(s["key"] == "video" for s in body["steps"])
