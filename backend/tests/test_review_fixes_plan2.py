"""Regression tests for plan-2 code-review fixes."""
from datetime import datetime, timezone

import pytest

from app.models import Account, Snapshot
from app.evaluation.scoring import (
    ScoringConfig,
    growth_score,
    engagement_score,
    commercial_score,
    evaluate_account,
)
from app.analysis.content import positioning_proxy_score


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snap(ts_day, followers=None, engagement_rate=None, conversions=None):
    return Snapshot(
        account_id=1,
        ts=datetime(2026, 7, ts_day, tzinfo=timezone.utc),
        followers=followers,
        engagement_rate=engagement_rate,
        conversions=conversions,
    )


def _account(weights=None):
    return Account(
        platform="x",
        handle="@test",
        objective_weights=weights or {
            "growth": 0.25, "engagement": 0.25, "commercial": 0.25, "positioning": 0.25
        },
    )


# ---------------------------------------------------------------------------
# Fix 1: zero-target guards — no ZeroDivisionError, return 0.0
# ---------------------------------------------------------------------------

def test_growth_score_zero_target_returns_zero():
    snaps = [_snap(1, followers=1000), _snap(2, followers=1100)]
    assert growth_score(snaps, ScoringConfig(target_growth_rate=0)) == 0.0


def test_growth_score_zero_target_float_returns_zero():
    snaps = [_snap(1, followers=1000), _snap(2, followers=1100)]
    assert growth_score(snaps, ScoringConfig(target_growth_rate=0.0)) == 0.0


def test_engagement_score_zero_target_returns_zero():
    snap = _snap(1, engagement_rate=0.05)
    assert engagement_score(snap, ScoringConfig(target_engagement_rate=0)) == 0.0


def test_engagement_score_zero_target_float_returns_zero():
    snap = _snap(1, engagement_rate=0.05)
    assert engagement_score(snap, ScoringConfig(target_engagement_rate=0.0)) == 0.0


def test_commercial_score_zero_target_returns_zero():
    snap = _snap(1, conversions=5)
    assert commercial_score(snap, ScoringConfig(target_conversions=0)) == 0.0


def test_commercial_score_zero_target_float_returns_zero():
    snap = _snap(1, conversions=5)
    assert commercial_score(snap, ScoringConfig(target_conversions=0.0)) == 0.0


# ---------------------------------------------------------------------------
# Fix 2: positioning_proxy_score([]) == 0.0
# ---------------------------------------------------------------------------

def test_positioning_proxy_score_empty_returns_zero():
    assert positioning_proxy_score([]) == 0.0


# ---------------------------------------------------------------------------
# Fix 1+2 via evaluate_account: empty snapshots + zero targets
# ---------------------------------------------------------------------------

def test_evaluate_account_empty_snapshots_no_raise():
    acc = _account()
    result = evaluate_account(acc, [], positioning_score=50.0)
    assert result.breakdown["growth"] == 0.0
    assert result.breakdown["engagement"] == 0.0
    assert result.breakdown["commercial"] == 0.0
    assert result.breakdown["positioning"] == 50.0


def test_evaluate_account_all_zero_targets_no_raise():
    acc = _account()
    cfg = ScoringConfig(target_growth_rate=0, target_engagement_rate=0, target_conversions=0)
    snaps = [_snap(1, followers=1000, engagement_rate=0.05, conversions=5),
             _snap(2, followers=1100, engagement_rate=0.05, conversions=5)]
    result = evaluate_account(acc, snaps, positioning_score=80.0, cfg=cfg)
    assert result.breakdown["growth"] == 0.0
    assert result.breakdown["engagement"] == 0.0
    assert result.breakdown["commercial"] == 0.0


# ---------------------------------------------------------------------------
# Fix: out-of-range positioning_score is clamped to [0, 100]
# ---------------------------------------------------------------------------

def test_evaluate_account_positioning_clamped_high():
    acc = _account()
    result = evaluate_account(acc, [], positioning_score=150.0)
    assert result.breakdown["positioning"] == 100.0


def test_evaluate_account_positioning_clamped_low():
    acc = _account()
    result = evaluate_account(acc, [], positioning_score=-20.0)
    assert result.breakdown["positioning"] == 0.0
