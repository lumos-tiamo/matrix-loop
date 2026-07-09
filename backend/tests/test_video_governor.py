import pytest

from app.models import Account, ChannelBrief, Draft, LoopRun, VideoAsset
from app.video.base import VideoQuotaExceeded, NearDuplicateScript
from app.video.fake import FakeVideoProvider
from app.video.governor import VideoConfig, generate_video


def _script_draft(session, account_id, content="crypto airdrop guide", status="adopted"):
    lr = LoopRun(account_id=account_id); session.add(lr); session.commit()
    d = Draft(loop_run_id=lr.id, kind="script", content=content, review_status=status)
    session.add(d); session.commit()
    return d


def _acct(session, handle="@x", vertical="crypto"):
    a = Account(platform="tiktok", handle=handle, vertical=vertical)
    session.add(a); session.commit()
    return a


def test_generate_requires_adopted_script(session):
    acc = _acct(session)
    d = _script_draft(session, acc.id, status="pending")
    with pytest.raises(ValueError):
        generate_video(session, acc, d, provider=FakeVideoProvider())


def test_generate_creates_ready_asset_and_meters_cost(session):
    acc = _acct(session)
    d = _script_draft(session, acc.id)
    asset = generate_video(session, acc, d, provider=FakeVideoProvider())
    assert asset.status == "ready" and asset.review_status == "pending"
    assert asset.provider == "fake" and asset.cost == 1.0 and asset.media_url
    assert asset.script_draft_id == d.id


def test_generate_dedups_identical_script(session):
    acc = _acct(session)
    d = _script_draft(session, acc.id)
    a1 = generate_video(session, acc, d, provider=FakeVideoProvider())
    a2 = generate_video(session, acc, d, provider=FakeVideoProvider())
    assert a1.id == a2.id                          # reused, not regenerated
    assert session.query(VideoAsset).count() == 1


def test_per_account_daily_quota(session):
    acc = _acct(session)
    cfg = VideoConfig(per_account_per_day=1)
    generate_video(session, acc, _script_draft(session, acc.id, "script one"), provider=FakeVideoProvider(), cfg=cfg)
    with pytest.raises(VideoQuotaExceeded):
        generate_video(session, acc, _script_draft(session, acc.id, "script two"), provider=FakeVideoProvider(), cfg=cfg)


def test_global_daily_quota(session):
    a1 = _acct(session, "@a1"); a2 = _acct(session, "@a2")
    cfg = VideoConfig(max_videos_per_day=1, per_account_per_day=5)
    generate_video(session, a1, _script_draft(session, a1.id, "one"), provider=FakeVideoProvider(), cfg=cfg)
    with pytest.raises(VideoQuotaExceeded):
        generate_video(session, a2, _script_draft(session, a2.id, "two"), provider=FakeVideoProvider(), cfg=cfg)


def test_near_duplicate_rejected(session):
    a1 = _acct(session, "@a1"); a2 = _acct(session, "@a2")
    generate_video(session, a1, _script_draft(session, a1.id, "crypto airdrop farming guide steps"),
                   provider=FakeVideoProvider())
    with pytest.raises(NearDuplicateScript):
        generate_video(session, a2, _script_draft(session, a2.id, "crypto airdrop farming guide steps"),
                       provider=FakeVideoProvider(), cfg=VideoConfig(dedup_similarity=0.8))
