from datetime import datetime, timezone

from app.models import Account, ContentItem, Snapshot
from app.loop.engine import run_loop


def test_loop_adds_content_performance_recommendation(session):
    acc = Account(platform="tiktok", handle="@x", objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc); session.commit()
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100),
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=140),
        ContentItem(account_id=acc.id, topic="airdrop guide", views=12000, likes=800),
        ContentItem(account_id=acc.id, topic="meme recap", views=200, likes=5),
    ]); session.commit()
    run = run_loop(session, acc)   # deterministic path (no llm)
    kinds = {r.kind for r in run.recommendations}
    assert "content_performance" in kinds
    perf_rec = next(r for r in run.recommendations if r.kind == "content_performance")
    assert "airdrop guide" in perf_rec.content        # names the top performer


def test_loop_no_perf_rec_when_no_view_data(session):
    acc = Account(platform="tiktok", handle="@y", objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc); session.commit()
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100))
    session.add(ContentItem(account_id=acc.id, topic="no views"))   # views None
    session.commit()
    run = run_loop(session, acc)
    assert "content_performance" not in {r.kind for r in run.recommendations}
