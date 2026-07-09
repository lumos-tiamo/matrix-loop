from datetime import datetime, timezone

from app.models import Account, ContentItem, Draft, FlywheelEvent, LoopRun, Snapshot, VideoAsset
from app.orchestrator.engine import advance_account, OrchestratorConfig


import json as _json

_ANALYSIS_JSON = _json.dumps({
    "positioning_clarity": 70,
    "positioning_label": "crypto airdrop",
    "content_direction": "focus on airdrop alpha",
    "suggested_topics": ["airdrop guide", "top airdrops 2026"],
})


class _LLM:
    def complete(self, *, system, prompt): return _ANALYSIS_JSON
    last_usage = {"input": 1, "output": 1}


class _Video:
    name = "seedance"
    def generate(self, *, script, brief, params):
        from app.video.base import VideoResult
        return VideoResult(media_url="https://cdn/x.mp4", duration=5, cost=1, provider="seedance",
                           dedup_key="d", metadata={})


class _Fake:
    name = "fake"
    def generate(self, *, script, brief, params):
        from app.video.base import VideoResult
        return VideoResult(media_url="https://fake.local/x.mp4", duration=5, cost=1, provider="fake",
                           dedup_key="d", metadata={})


class _AiToEarn:
    def publish_flow(self, payload):
        return {"flowId": "f1", "tasks": [{"id": "t1", "status": "WaitingForPublish"}]}
    def flow_status(self, fid): return {"tasks": [{"id": "t1", "status": "Published", "platformWorkId": "w9"}]}


def _acct(session, handle="@x", autopilot=False, external_ref="ae_1"):
    a = Account(platform="tiktok", handle=handle, autopilot=autopilot, external_ref=external_ref,
                objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(a); session.commit()
    session.add_all([
        Snapshot(account_id=a.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100),
        ContentItem(account_id=a.id, topic="airdrop", views=5000),
    ]); session.commit()
    return a


def test_non_autopilot_stops_at_review_queue(session):
    a = _acct(session, autopilot=False)
    rep = advance_account(session, a, llm=_LLM(), video=_Fake(), aitoearn=None, sync=False)
    assert rep["reached_step"] in ("evaluate", "topic")   # produced drafts, did NOT auto-advance
    # no video asset, no dispatch created
    assert session.query(VideoAsset).count() == 0
    # a topic draft exists (from the loop) but is NOT auto-adopted
    topics = session.query(Draft).filter_by(kind="topic").all()
    assert topics and all(d.review_status != "adopted" for d in topics)


def test_autopilot_advances_through_publish_with_real_video(session):
    a = _acct(session, autopilot=True, external_ref="ae_1")
    rep = advance_account(session, a, llm=_LLM(), video=_Video(), aitoearn=_AiToEarn(),
                          sync=False, cfg=OrchestratorConfig())
    assert rep["reached_step"] == "publish"
    # a script draft was auto-adopted, a video generated + approved, a dispatch created
    assert session.query(Draft).filter_by(kind="script").filter(Draft.review_status == "adopted").count() >= 1
    v = session.query(VideoAsset).one()
    assert v.review_status == "approved" and v.provider == "seedance"
    from app.models import PublishDispatch
    assert session.query(PublishDispatch).count() == 1
    # audit trail recorded steps
    steps = [e.step for e in session.query(FlywheelEvent).order_by(FlywheelEvent.id).all()]
    assert "script" in steps and "video" in steps and "publish" in steps


def test_autopilot_does_not_publish_fake_video(session):
    a = _acct(session, autopilot=True, external_ref="ae_1")
    rep = advance_account(session, a, llm=_LLM(), video=_Fake(), aitoearn=_AiToEarn(),
                          sync=False, cfg=OrchestratorConfig(allow_fake_publish=False))
    assert rep["reached_step"] == "video"           # produced fake video, refused to publish it
    from app.models import PublishDispatch
    assert session.query(PublishDispatch).count() == 0
    blocked = [e for e in session.query(FlywheelEvent).all() if e.status == "blocked"]
    assert any("fake" in (e.detail or "").lower() or e.step == "publish" for e in blocked)


def test_autopilot_blocks_publish_without_aitoearn(session):
    a = _acct(session, autopilot=True, external_ref="ae_1")
    rep = advance_account(session, a, llm=_LLM(), video=_Video(), aitoearn=None, sync=False)
    assert rep["reached_step"] == "approve"          # video approved but no AiToEarn -> can't publish
    from app.models import PublishDispatch
    assert session.query(PublishDispatch).count() == 0


def test_autopilot_without_llm_stops_at_topic(session):
    a = _acct(session, autopilot=True)
    rep = advance_account(session, a, llm=None, video=_Video(), aitoearn=_AiToEarn(), sync=False)
    assert rep["reached_step"] in ("evaluate", "topic")   # no LLM -> no script -> no video/publish
    assert session.query(VideoAsset).count() == 0
