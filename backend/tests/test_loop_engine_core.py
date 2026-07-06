from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem, LoopRun
from app.loop.engine import run_loop


def _seed(session, weights=None):
    acc = Account(platform="xiaohongshu", handle="@a1",
                  objective_weights=weights or {"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100000),
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110000),  # +10% -> growth 100
        ContentItem(account_id=acc.id, views=100, topic="beauty"),
        ContentItem(account_id=acc.id, views=100, topic="beauty"),
        ContentItem(account_id=acc.id, views=1000, topic="beauty"),  # 爆文
    ])
    session.commit()
    return acc


def test_run_loop_persists_loop_run_with_evaluation(session):
    acc = _seed(session)
    run = run_loop(session, acc)
    assert isinstance(run, LoopRun)
    assert run.id is not None
    assert run.evaluation is not None
    assert run.evaluation.composite_score == 100.0  # weights all on growth, +10% -> 100
    assert run.diagnosis  # non-empty
    assert session.query(LoopRun).count() == 1


def test_run_loop_produces_recommendations_and_hit_cadence(session):
    acc = _seed(session)
    run = run_loop(session, acc)
    kinds = [r.kind for r in run.recommendations]
    assert "content_direction" in kinds
    assert "cadence" in kinds  # 有一条爆文 -> cadence 建议
    # 确定性路径不产出草稿（草稿来自 LLM suggested_topics）
    assert run.drafts == []


def test_run_loop_first_run_verify_is_baseline(session):
    acc = _seed(session)
    run = run_loop(session, acc)
    assert run.verify_result.get("baseline") is True
    assert run.status == "ok"
