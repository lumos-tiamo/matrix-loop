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


def test_estimate_batch_counts_cost():
    from app.video.governor import estimate_batch
    est = estimate_batch(4, per_video_cost=1.0)
    assert est == {"count": 4, "estimated_cost": 4.0}


def test_run_video_batch_stops_on_budget(session):
    from app.video.governor import run_video_batch, VideoConfig
    accts = [_acct(session, f"@b{i}") for i in range(5)]
    drafts = [_script_draft(session, a.id, f"unique script number {i} about defi yields")
              for i, a in enumerate(accts)]
    pairs = list(zip(accts, drafts))
    # budget 2.0 with fake cost 1.0 each -> stops after the run that crosses the budget
    report = run_video_batch(session, pairs, provider=FakeVideoProvider(),
                             cfg=VideoConfig(video_budget=2.0, per_account_per_day=5, max_videos_per_day=99))
    assert report["stopped_early"] is True
    assert report["generated"] == 2
    assert report["total_cost"] == 2.0


def test_run_video_batch_isolates_failures(session):
    from app.video.governor import run_video_batch, VideoConfig
    a_ok = _acct(session, "@ok"); a_pending = _acct(session, "@pending")
    d_ok = _script_draft(session, a_ok.id, "airdrop hunting checklist")
    d_pending = _script_draft(session, a_pending.id, "meme coin cycle", status="pending")  # not adopted
    report = run_video_batch(session, [(a_pending, d_pending), (a_ok, d_ok)],
                             provider=FakeVideoProvider(), cfg=VideoConfig(video_budget=99))
    assert report["generated"] == 1
    assert len(report["errors"]) == 1


def test_usage_summary_reports_today_and_total(session):
    from app.video.governor import usage_summary, VideoConfig
    acc = _acct(session)
    generate_video(session, acc, _script_draft(session, acc.id, "unique defi explainer"),
                   provider=FakeVideoProvider())
    summ = usage_summary(session, cfg=VideoConfig())
    assert summ["today_count"] == 1 and summ["today_cost"] == 1.0
    assert summ["total_count"] == 1
    assert summ["caps"]["max_videos_per_day"] == 20
