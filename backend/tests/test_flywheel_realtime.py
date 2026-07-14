from datetime import datetime, timezone, timedelta
from app.orchestrator.state import flywheel_accounts

def _utc(): return datetime.now(timezone.utc)

def test_flywheel_accounts_running(session):
    from app.models import Account, FlywheelEvent
    a = Account(platform="tiktok", handle="@nina_web3", autopilot=True); session.add(a); session.flush()
    cid = "cyc1"
    for step, st in [("sync","ok"),("evaluate","ok"),("topic","ok"),("script","ok")]:
        session.add(FlywheelEvent(account_id=a.id, cycle_id=cid, step=step, status=st))
    session.commit()
    rows = flywheel_accounts(session)
    row = next(r for r in rows if r["account_id"] == a.id)
    assert row["status"] == "running"
    assert row["current_step"] == "video"
    assert row["steps_done"] == 4
    assert row["handle"] == "@nina_web3"

def test_flywheel_accounts_blocked(session):
    from app.models import Account, FlywheelEvent
    a = Account(platform="twitter", handle="@xaue_gold", autopilot=True); session.add(a); session.flush()
    for step, st in [("sync","ok"),("evaluate","ok"),("topic","ok"),("script","ok"),("video","ok"),("approve","blocked")]:
        session.add(FlywheelEvent(account_id=a.id, cycle_id="c2", step=step, status=st, detail="待人工审核"))
    session.commit()
    row = next(r for r in flywheel_accounts(session) if r["account_id"] == a.id)
    assert row["status"] == "blocked"
    assert row["current_step"] == "approve"
    assert row["blocked_reason"] == "待人工审核"

def test_flywheel_accounts_only_autopilot(session):
    from app.models import Account
    session.add(Account(platform="yt", handle="@manual", autopilot=False)); session.commit()
    assert all(r["handle"] != "@manual" for r in flywheel_accounts(session))


def test_flywheel_events_since_and_filter(session):
    from app.models import Account, FlywheelEvent
    from app.orchestrator.state import flywheel_events_since
    a = Account(platform="tiktok", handle="@n", autopilot=True); session.add(a); session.flush()
    for step in ["sync", "evaluate", "topic"]:
        session.add(FlywheelEvent(account_id=a.id, cycle_id="c", step=step, status="ok"))
    session.commit()
    all_ev = flywheel_events_since(session, since_id=None, account_id=None, limit=50)
    assert len(all_ev) == 3
    assert all_ev[0]["account_handle"] == "@n"
    max_id = max(e["id"] for e in all_ev)
    assert flywheel_events_since(session, since_id=max_id, account_id=None, limit=50) == []
    assert len(flywheel_events_since(session, since_id=None, account_id=a.id, limit=50)) == 3


def test_flywheel_state_has_today_cost_and_counts(session):
    from app.models import Account, VideoAsset
    from app.orchestrator.state import flywheel_state
    a = Account(platform="tiktok", handle="@n", autopilot=True); session.add(a); session.flush()
    session.add(VideoAsset(account_id=a.id, provider="faceless", cost=0.42, status="ready"))
    session.commit()
    st = flywheel_state(session)
    assert "today_cost" in st and st["today_cost"] >= 0.42
    assert "status_counts" in st
