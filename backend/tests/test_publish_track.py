from app.models import Account, Calibration, ContentItem, PublishDispatch, VideoAsset, _utcnow
from app.publish.track import track_summary


def _seed_published(session):
    acc = Account(platform="tiktok", handle="@tk")
    session.add(acc)
    session.commit()
    asset = VideoAsset(account_id=acc.id, provider="fake", media_url="http://x/v.mp4",
                       status="ready", review_status="approved")
    session.add(asset)
    session.commit()
    session.add(PublishDispatch(account_id=acc.id, video_asset_id=asset.id, status="published",
                                platform_work_id="W1", caption="cap", publish_at=_utcnow(),
                                media_urls=["http://x/v.mp4"]))
    session.add(ContentItem(account_id=acc.id, video_asset_id=asset.id, views=1000,
                            likes=80, comments=15, saves=5, published_at=_utcnow()))
    cal = Calibration(video_asset_id=asset.id, account_id=acc.id, rubric_version="v1",
                      quality_score=75.0, predicted={"views": 800, "engagement_rate": 0.05},
                      actual={"views": 1000}, error={"views": 25.0},
                      calibration_error=25.0, status="reviewed")
    session.add(cal)
    session.commit()
    return acc, asset


def test_track_summary_joins_all_layers(session):
    acc, asset = _seed_published(session)
    s = track_summary(session)
    assert s["total_published"] == 1
    assert s["platforms"] == {"tiktok": 1}
    assert s["reviewed"] == 1
    w = s["works"][0]
    assert w["platform"] == "tiktok"
    assert w["actual"]["views"] == 1000
    assert w["actual"]["engagement_rate"] == 0.1        # (80+15+5)/1000
    assert w["predicted"]["views"] == 800
    assert w["quality_score"] == 75.0
    assert w["prediction_error"]["views"] == 25.0


def test_track_summary_filters_by_account(session):
    acc, asset = _seed_published(session)
    other = Account(platform="x", handle="@other")
    session.add(other)
    session.commit()
    assert track_summary(session, account_id=other.id)["total_published"] == 0
    assert track_summary(session, account_id=acc.id)["total_published"] == 1
