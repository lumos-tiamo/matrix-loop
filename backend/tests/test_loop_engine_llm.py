import json
from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem
from app.loop.engine import run_loop


class FakeLLMClient:
    def __init__(self, response): self.response = response
    def complete(self, *, system, prompt): return self.response


def test_run_loop_llm_path_enriches_outputs(session):
    acc = Account(platform="xiaohongshu", handle="@a1", objective_weights={
        "growth": 0.0, "engagement": 0.0, "commercial": 0.0, "positioning": 1.0})
    session.add(acc)
    session.commit()
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=100000),
        ContentItem(account_id=acc.id, views=100, topic="beauty"),
    ])
    session.commit()

    client = FakeLLMClient(json.dumps({
        "positioning_clarity": 72,
        "positioning_label": "平价美妆测评",
        "content_direction": "聚焦百元内产品横评",
        "suggested_topics": ["5款百元粉底横评", "学生党护肤清单"],
    }))

    run = run_loop(session, acc, llm_client=client)

    # positioning 权重 1.0 -> 复合分 == LLM 清晰度 72
    assert run.evaluation.composite_score == 72.0
    assert "平价美妆测评" in run.diagnosis
    kinds = {r.kind for r in run.recommendations}
    assert {"positioning", "content_direction"} <= kinds
    # suggested_topics -> 两条草稿
    topics = sorted(d.content for d in run.drafts if d.kind == "topic")
    assert topics == ["5款百元粉底横评", "学生党护肤清单"]
