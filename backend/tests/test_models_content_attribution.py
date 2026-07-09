from app.models import Account, ContentItem, Draft, LoopRun, VideoAsset


def test_content_item_attribution_columns(session):
    acc = Account(platform="tiktok", handle="@x"); session.add(acc); session.commit()
    lr = LoopRun(account_id=acc.id); session.add(lr); session.commit()
    d = Draft(loop_run_id=lr.id, kind="script", content="s"); session.add(d); session.commit()
    v = VideoAsset(account_id=acc.id, script_draft_id=d.id, provider="fake", dedup_key="k"); session.add(v); session.commit()
    ci = ContentItem(account_id=acc.id, platform_post_id="w1", views=100, video_asset_id=v.id, draft_id=d.id)
    session.add(ci); session.commit()
    got = session.get(ContentItem, ci.id)
    assert got.video_asset_id == v.id and got.draft_id == d.id
    # defaults to None when unset
    ci2 = ContentItem(account_id=acc.id, topic="t"); session.add(ci2); session.commit()
    assert ci2.video_asset_id is None and ci2.draft_id is None
