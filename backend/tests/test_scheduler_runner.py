from apscheduler.schedulers.base import SchedulerNotRunningError

from app.scheduler.runner import build_scheduler


def test_build_scheduler_registers_one_job():
    called = {}

    def fake_session_factory():
        raise AssertionError("should not be called at build time")

    scheduler = build_scheduler(fake_session_factory, interval_minutes=15)
    try:
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        # interval trigger reflects the configured minutes
        assert "15" in str(jobs[0].trigger) or jobs[0].trigger.interval.total_seconds() == 15 * 60
    finally:
        try:
            scheduler.shutdown(wait=False)
        except SchedulerNotRunningError:
            pass  # never started — nothing to shut down
    assert called == {}  # session factory not invoked merely by building
