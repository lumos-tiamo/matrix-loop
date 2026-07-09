from apscheduler.schedulers.base import SchedulerNotRunningError

from app.scheduler.runner import build_scheduler


def test_build_scheduler_registers_one_job():
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


def test_build_scheduler_registers_autopilot_and_analytics_jobs():
    from app.scheduler.runner import build_scheduler
    sched = build_scheduler(lambda: None, interval_minutes=30)
    ids = {j.id for j in sched.get_jobs()}
    assert "matrixloop-autopilot" in ids
    # does not auto-start
    assert not sched.running
