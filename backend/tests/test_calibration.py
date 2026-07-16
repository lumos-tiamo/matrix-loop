from datetime import timedelta

from app.calibration import calibrator, rubric as rubric_mod
from app.models import Account, ContentItem, Draft, LoopRun, VideoAsset, _utcnow


_SEQ = [0]


def _seed_asset(session, script="开场钩子是什么?3个空投技巧,关注主页领取。\n第二句正文内容更多信息。"):
    _SEQ[0] += 1
    acc = Account(platform="x", handle=f"@cal{_SEQ[0]}")
    session.add(acc)
    session.commit()
    run = LoopRun(account_id=acc.id, status="ok")
    run.drafts.append(Draft(kind="script", content=script, review_status="adopted"))
    session.add(run)
    session.commit()
    draft = run.drafts[0]
    asset = VideoAsset(account_id=acc.id, script_draft_id=draft.id, provider="fake",
                       media_url="http://x/v.mp4", status="ready", review_status="approved")
    session.add(asset)
    session.commit()
    return acc, asset


def test_score_and_predict_is_blind_and_frozen(session):
    acc, asset = _seed_asset(session)
    cal = calibrator.score_and_predict(session, asset)
    assert cal.status == "predicted"
    assert 0 <= cal.quality_score <= 100
    assert "views" in cal.predicted and "engagement_rate" in cal.predicted
    assert cal.rubric_version == rubric_mod.rubric_version(session)
    assert cal.actual == {}  # no real data at prediction time
    # idempotent: second call returns the same frozen row
    again = calibrator.score_and_predict(session, asset)
    assert again.id == cal.id
    assert again.predicted == cal.predicted


def test_gate_blocks_low_quality(session):
    acc, asset = _seed_asset(session, script="嗯。")  # threadbare script -> low score
    cal = calibrator.gate(session, asset)
    # raise threshold above any plausible score to force a block, then re-gate a fresh asset
    rubric_mod.bump_rubric(session, threshold=99.0, note="test high bar")
    _, asset2 = _seed_asset(session, script="短。")
    cal2 = calibrator.gate(session, asset2)
    assert cal2.gate_passed is False


def test_review_computes_prediction_error(session):
    acc, asset = _seed_asset(session)
    cal = calibrator.score_and_predict(session, asset)
    cal.predicted = {"views": 1000, "engagement_rate": 0.05}
    session.commit()
    reviewed = calibrator.review(session, cal, actual={"views": 1500, "engagement_rate": 0.04})
    assert reviewed.status == "reviewed"
    assert reviewed.error["views"] == 50.0            # +50% vs prediction
    assert reviewed.error["engagement_rate"] == -20.0
    assert reviewed.calibration_error == 35.0         # mean abs
    assert reviewed.reviewed_at is not None


def test_review_pulls_actual_from_content_item(session):
    acc, asset = _seed_asset(session)
    cal = calibrator.score_and_predict(session, asset)
    session.add(ContentItem(account_id=acc.id, video_asset_id=asset.id,
                            views=800, likes=30, comments=5, saves=5,
                            published_at=_utcnow()))
    session.commit()
    reviewed = calibrator.review(session, cal)
    assert reviewed.actual["views"] == 800
    assert reviewed.calibration_error is not None


def test_pending_reviews_respects_age(session):
    acc, asset = _seed_asset(session)
    cal = calibrator.score_and_predict(session, asset)
    assert calibrator.pending_reviews(session, min_age_days=3) == []   # just locked
    cal.locked_at = _utcnow() - timedelta(days=5)
    session.commit()
    due = calibrator.pending_reviews(session, min_age_days=3)
    assert len(due) == 1 and due[0].id == cal.id


def test_evolve_rubric_bumps_version(session):
    v0 = rubric_mod.rubric_version(session)
    # seed 3 reviewed works that over-performed -> evolution should move + bump version
    for i in range(3):
        _, asset = _seed_asset(session)
        cal = calibrator.score_and_predict(session, asset)
        cal.predicted = {"views": 100, "engagement_rate": 0.05}
        session.commit()
        calibrator.review(session, cal, actual={"views": 300, "engagement_rate": 0.06})
    new = calibrator.evolve_rubric(session)
    assert new["version"] != v0
    assert any("auto-evolve" in c for c in new["changelog"])
    # old calibrations now flagged for re-score (principle 2)
    assert len(calibrator.needs_rescore(session)) == 3


def test_evolve_requires_min_reviews(session):
    import pytest
    with pytest.raises(ValueError):
        calibrator.evolve_rubric(session)


def test_summary_shape(session):
    acc, asset = _seed_asset(session)
    calibrator.score_and_predict(session, asset)
    s = calibrator.calibration_summary(session)
    assert s["total"] == 1 and "rubric_version" in s and "threshold" in s
