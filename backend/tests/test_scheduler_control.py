import pytest
from app.scheduler import control


@pytest.fixture(autouse=True)
def _stop_scheduler_after_each():
    """Ensure no scheduler thread leaks between tests."""
    yield
    control.stop_scheduler()


def test_scheduler_control_start_stop():
    control.stop_scheduler()                      # idempotent even if not started
    assert control.scheduler_running() is False
    control.start_scheduler(lambda: None, interval_minutes=60)
    assert control.scheduler_running() is True
    # idempotent start
    control.start_scheduler(lambda: None, interval_minutes=60)
    assert control.scheduler_running() is True
    control.stop_scheduler()
    assert control.scheduler_running() is False


def test_scheduler_api_start_status_stop(client):
    assert client.get("/flywheel/status").json().get("scheduler_running") is False
    r = client.post("/flywheel/scheduler/start")
    assert r.status_code == 200 and r.json()["scheduler_running"] is True
    assert client.get("/flywheel/status").json()["scheduler_running"] is True
    assert client.post("/flywheel/scheduler/stop").json()["scheduler_running"] is False
