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
