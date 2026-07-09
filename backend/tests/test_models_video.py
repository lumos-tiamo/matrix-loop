from app.models import Account, ChannelBrief, VideoAsset


def test_channel_brief_defaults_and_persist(session):
    acc = Account(platform="youtube", handle="@nina")
    session.add(acc); session.commit()
    b = ChannelBrief(account_id=acc.id, main_direction="web3",
                     sub_niches=["加密交易者", "空投猎人", "DeFi"], persona="Nina")
    session.add(b); session.commit()
    got = session.get(ChannelBrief, b.id)
    assert got.main_direction == "web3"
    assert got.sub_niches == ["加密交易者", "空投猎人", "DeFi"]
    assert got.language == "en"                 # default
    assert got.format == "faceless"             # default
    assert got.compliance_stance == "info_education"


def test_channel_brief_sub_niches_default_empty(session):
    acc = Account(platform="tiktok", handle="@z")
    session.add(acc); session.commit()
    b = ChannelBrief(account_id=acc.id, main_direction="web3")
    session.add(b); session.commit()
    assert b.sub_niches == []


def test_video_asset_defaults_and_persist(session):
    acc = Account(platform="tiktok", handle="@x")
    session.add(acc); session.commit()
    v = VideoAsset(account_id=acc.id, provider="fake", media_url="https://f/x.mp4",
                   duration=45.0, cost=1.0, dedup_key="abc")
    session.add(v); session.commit()
    got = session.get(VideoAsset, v.id)
    assert got.status == "ready"                 # default
    assert got.review_status == "pending"        # default
    assert got.cost == 1.0 and got.dedup_key == "abc"
