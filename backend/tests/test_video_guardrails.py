from app.video.guardrails import assign_voice, script_similarity, is_near_duplicate_script


VOICES = ["v_alloy", "v_echo", "v_fable", "v_onyx", "v_nova"]


def test_assign_voice_deterministic_and_in_pool():
    a = assign_voice(1, VOICES)
    assert a in VOICES
    assert assign_voice(1, VOICES) == a                      # deterministic
    # different accounts spread across the pool (not all identical)
    assigned = {assign_voice(i, VOICES) for i in range(1, 20)}
    assert len(assigned) >= 3


def test_assign_voice_empty_pool_returns_default():
    assert assign_voice(1, []) == "default"


def test_script_similarity_scores_overlap():
    assert script_similarity("the quick brown fox", "the quick brown fox") == 1.0
    assert script_similarity("alpha beta gamma", "delta epsilon zeta") == 0.0
    mid = script_similarity("crypto airdrop guide today", "crypto airdrop guide tomorrow")
    assert 0.5 < mid < 1.0


def test_is_near_duplicate_flags_similar_other_account(session):
    from app.models import Account, VideoAsset, Draft, LoopRun, ChannelBrief  # noqa: F401
    a1 = Account(platform="tiktok", handle="@a1"); a2 = Account(platform="tiktok", handle="@a2")
    session.add_all([a1, a2]); session.commit()
    lr = LoopRun(account_id=a1.id); session.add(lr); session.commit()
    d = Draft(loop_run_id=lr.id, kind="script", content="crypto airdrop farming guide step by step")
    session.add(d); session.commit()
    session.add(VideoAsset(account_id=a1.id, script_draft_id=d.id, provider="fake",
                           dedup_key="k1", status="ready")); session.commit()
    # a2 attempts a near-identical script -> flagged
    assert is_near_duplicate_script(session, a2.id,
        "crypto airdrop farming guide step by step now", threshold=0.8) is True
    # a distinct script -> not flagged
    assert is_near_duplicate_script(session, a2.id,
        "defi yield strategies explained", threshold=0.8) is False
    # same account's own script does NOT count as a cross-account duplicate
    assert is_near_duplicate_script(session, a1.id,
        "crypto airdrop farming guide step by step", threshold=0.8) is False
