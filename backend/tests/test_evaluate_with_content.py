from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem
from app.evaluation.scoring import evaluate_with_content


def test_evaluate_with_content_uses_positioning_proxy():
    acc = Account(platform="xiaohongshu", handle="@a", objective_weights={
        "growth": 0.0, "engagement": 0.0, "commercial": 0.0, "positioning": 1.0
    })
    snaps = [
        Snapshot(account_id=1, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100),
        Snapshot(account_id=1, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110),
    ]
    focused = [ContentItem(account_id=1, views=100, topic="beauty")] * 4
    result = evaluate_with_content(acc, snaps, focused)
    # 权重全压 positioning，focused 内容 → positioning=100 → composite=100
    assert result.breakdown["positioning"] == 100.0
    assert result.composite_score == 100.0
