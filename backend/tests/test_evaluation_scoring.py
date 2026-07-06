from datetime import datetime, timezone

from app.models import Account, Snapshot
from app.evaluation.scoring import (
    ScoringConfig,
    growth_score,
    engagement_score,
    commercial_score,
    evaluate_account,
)


def _snap(ts_day, followers=None, engagement_rate=None, conversions=None):
    return Snapshot(
        account_id=1,
        ts=datetime(2026, 7, ts_day, tzinfo=timezone.utc),
        followers=followers,
        engagement_rate=engagement_rate,
        conversions=conversions,
    )


def test_growth_score_hits_100_at_target():
    cfg = ScoringConfig(target_growth_rate=0.10)
    snaps = [_snap(1, followers=100000), _snap(6, followers=110000)]  # +10%
    assert growth_score(snaps, cfg) == 100.0


def test_growth_score_zero_with_single_snapshot():
    assert growth_score([_snap(1, followers=100000)], ScoringConfig()) == 0.0


def test_engagement_score_scales_and_clamps():
    cfg = ScoringConfig(target_engagement_rate=0.05)
    assert engagement_score(_snap(6, engagement_rate=0.025), cfg) == 50.0
    assert engagement_score(_snap(6, engagement_rate=0.20), cfg) == 100.0  # clamped


def test_commercial_score():
    cfg = ScoringConfig(target_conversions=10)
    assert commercial_score(_snap(6, conversions=5), cfg) == 50.0


def test_evaluate_account_weighted_composite():
    acc = Account(platform="x", handle="@a", objective_weights={
        "growth": 0.4, "engagement": 0.3, "commercial": 0.2, "positioning": 0.1
    })
    snaps = [_snap(1, followers=100000, engagement_rate=0.05, conversions=10),
             _snap(6, followers=110000, engagement_rate=0.05, conversions=10)]
    result = evaluate_account(acc, snaps, positioning_score=80.0)
    # growth=100, engagement=100, commercial=100, positioning=80
    # composite = 0.4*100 + 0.3*100 + 0.2*100 + 0.1*80 = 98.0
    assert result.breakdown == {"growth": 100.0, "engagement": 100.0, "commercial": 100.0, "positioning": 80.0}
    assert result.composite_score == 98.0
