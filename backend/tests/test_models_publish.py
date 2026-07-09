from app.models import Account, PublishDispatch, VideoAsset


def test_publish_dispatch_defaults_and_persist(session):
    acc = Account(platform="tiktok", handle="@x")
    session.add(acc); session.commit()
    v = VideoAsset(account_id=acc.id, provider="fake", media_url="https://f/x.mp4", dedup_key="k")
    session.add(v); session.commit()
    d = PublishDispatch(account_id=acc.id, video_asset_id=v.id, caption="gm",
                        media_urls=["https://f/x.mp4"])
    session.add(d); session.commit()
    got = session.get(PublishDispatch, d.id)
    assert got.status == "pending"                 # default
    assert got.media_urls == ["https://f/x.mp4"]
    assert got.aitoearn_flow_id is None and got.platform_work_id is None


def test_publish_dispatch_media_urls_default_empty(session):
    acc = Account(platform="tiktok", handle="@y")
    session.add(acc); session.commit()
    d = PublishDispatch(account_id=acc.id)
    session.add(d); session.commit()
    assert d.media_urls == []
