import json
from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem
from app.evaluation.scoring import evaluate_with_analysis
from app.analysis.llm import AnalysisResult


class FakeLLMClient:
    def __init__(self, response): self.response = response
    def complete(self, *, system, prompt): return self.response


def test_evaluate_with_analysis_uses_llm_positioning():
    acc = Account(platform="x", handle="@a", objective_weights={
        "growth": 0.0, "engagement": 0.0, "commercial": 0.0, "positioning": 1.0
    })
    snaps = [Snapshot(account_id=1, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=100)]
    content = [ContentItem(account_id=1, views=100, topic="beauty")]
    client = FakeLLMClient(json.dumps({
        "positioning_clarity": 64,
        "positioning_label": "平价美妆",
        "content_direction": "聚焦横评",
        "suggested_topics": ["A", "B"],
    }))

    result, analysis = evaluate_with_analysis(acc, snaps, content, client)

    assert isinstance(analysis, AnalysisResult)
    assert analysis.positioning_label == "平价美妆"
    # weights all on positioning; positioning sub-score == LLM clarity 64
    assert result.breakdown["positioning"] == 64.0
    assert result.composite_score == 64.0
