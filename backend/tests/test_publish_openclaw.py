import pytest

from app.models import Account, Calibration, ContentItem, Draft, LoopRun, PublishDispatch, VideoAsset, _utcnow
from app.publish.dispatch import PublishNotReady
from app.publish.openclaw import publish_via_openclaw


def _seed(session, review_status="approved"):
    acc = Account(platform="x", handle="@oc")
    session.add(acc)
    session.commit()
    asset = VideoAsset(account_id=acc.id, provider="fake", media_url="http://x/v.mp4",
                       status="ready", review_status=review_status)
    session.add(asset)
    session.commit()
    return acc, asset


def test_publish_records_dispatch(session):
    acc, asset = _seed(session)
    posts = []

    def poster(path, payload):
        posts.append((path, payload))
        return {"work_id": "W123", "status": "published"}

    d = publish_via_openclaw(session, acc, asset, platform="tiktok", caption="hi", poster=poster)
    assert d.status == "published" and d.platform_work_id == "W123"
    assert posts[0][0] == "/publish" and posts[0][1]["platform"] == "tiktok"
    assert session.query(PublishDispatch).count() == 1


def test_requires_approval(session):
    acc, asset = _seed(session, review_status="pending")
    with pytest.raises(PublishNotReady):
        publish_via_openclaw(session, acc, asset, poster=lambda p, x: {})


def test_quality_gate_blocks(session):
    acc, asset = _seed(session)
    session.add(Calibration(video_asset_id=asset.id, account_id=acc.id, rubric_version="v1",
                            quality_score=10.0, gate_passed=False, status="predicted"))
    session.commit()
    with pytest.raises(PublishNotReady):
        publish_via_openclaw(session, acc, asset, enforce_gate=True, poster=lambda p, x: {})


def test_no_double_publish(session):
    acc, asset = _seed(session)
    publish_via_openclaw(session, acc, asset, poster=lambda p, x: {"work_id": "A", "status": "published"})
    with pytest.raises(PublishNotReady):
        publish_via_openclaw(session, acc, asset, poster=lambda p, x: {"work_id": "B"})


def test_publish_marks_calibration_published(session):
    acc, asset = _seed(session)
    cal = Calibration(video_asset_id=asset.id, account_id=acc.id, rubric_version="v1",
                      quality_score=80.0, gate_passed=True, status="predicted")
    session.add(cal)
    session.commit()
    publish_via_openclaw(session, acc, asset, poster=lambda p, x: {"work_id": "A", "status": "published"})
    session.refresh(cal)
    assert cal.status == "published"
