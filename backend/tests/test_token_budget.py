import json
from datetime import datetime, timezone

from app.models import Account, Snapshot
from app.loop.engine import run_loop
from app.scheduler.batch import run_batch, BatchConfig


class FakeUsageClient:
    """LLMClient exposing last_usage like ClaudeClient does."""
    def __init__(self, response, usage): self.response = response; self.last_usage = usage
    def complete(self, *, system, prompt): return self.response


VALID = json.dumps({"positioning_clarity": 70, "positioning_label": "x", "content_direction": "y", "suggested_topics": []})


def _acct(session, handle):
    acc = Account(platform="x", handle=handle, objective_weights={
        "growth": 0.0, "engagement": 0.0, "commercial": 0.0, "positioning": 1.0})
    session.add(acc); session.commit()
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=1000))
    session.commit()
    return acc


def test_run_loop_records_tokens_from_client(session):
    acc = _acct(session, "@a")
    client = FakeUsageClient(VALID, {"input": 120, "output": 30})
    run = run_loop(session, acc, llm_client=client)
    assert run.tokens_cost == 150


def test_run_loop_deterministic_zero_tokens(session):
    acc = _acct(session, "@b")
    run = run_loop(session, acc)     # no llm_client
    assert run.tokens_cost == 0


def test_batch_token_budget_stops(session, monkeypatch):
    for h in ("@a", "@b", "@c"):
        _acct(session, h)
    import app.scheduler.batch as batch_mod

    def fake_loop(sess, account, **kw):
        from app.models import LoopRun, Evaluation
        run = LoopRun(account_id=account.id, status="ok", tokens_cost=100)
        run.evaluation = Evaluation(account_id=account.id, composite_score=50.0, breakdown={})
        sess.add(run); sess.commit()
        return run

    monkeypatch.setattr(batch_mod, "run_loop", fake_loop)
    report = run_batch(session, sync=False, batch_cfg=BatchConfig(token_budget=150))
    # after 2nd account cumulative tokens=200 > 150 -> stop
    assert report.total_tokens >= 150
    assert report.stopped_early is True
    assert report.looped == 2
