from app.models import Account, AppState, FlywheelEvent


def test_account_autopilot_default_false(session):
    a = Account(platform="tiktok", handle="@x"); session.add(a); session.commit()
    assert a.autopilot is False
    a.autopilot = True; session.commit()
    assert session.get(Account, a.id).autopilot is True


def test_appstate_key_value(session):
    session.add(AppState(key="flywheel_paused", value="1")); session.commit()
    row = session.get(AppState, "flywheel_paused")
    assert row.value == "1"


def test_flywheel_event_persist(session):
    a = Account(platform="tiktok", handle="@x"); session.add(a); session.commit()
    ev = FlywheelEvent(account_id=a.id, cycle_id="c1", step="script", status="ok", detail="generated")
    session.add(ev); session.commit()
    got = session.query(FlywheelEvent).one()
    assert got.step == "script" and got.status == "ok" and got.account_id == a.id
