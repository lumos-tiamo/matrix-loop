import pytest

from app.models import Account, PublishDispatch, VideoAsset
from app.publish.dispatch import create_dispatch, refresh_dispatch, PublishNotReady


class _FakeClient:
    def __init__(self): self.published = None
    def publish_flow(self, payload):
        self.published = payload
        return {"flowId": "f1", "tasks": [{"id": "t1", "platform": "tiktok", "status": "WaitingForPublish"}]}
    def flow_status(self, flow_id):
        return {"flowId": flow_id, "tasks": [{"id": "t1", "status": "Published", "platformWorkId": "w9"}]}


def _approved_asset(session, external_ref="ae_1"):
    acc = Account(platform="tiktok", handle="@x", external_ref=external_ref)
    session.add(acc); session.commit()
    v = VideoAsset(account_id=acc.id, provider="fake", media_url="https://f/x.mp4",
                   dedup_key="k", status="ready", review_status="approved")
    session.add(v); session.commit()
    return acc, v


def test_create_dispatch_requires_approved_asset(session):
    acc = Account(platform="tiktok", handle="@x", external_ref="ae_1")
    session.add(acc); session.commit()
    v = VideoAsset(account_id=acc.id, provider="fake", media_url="https://f/x.mp4",
                   dedup_key="k", status="ready", review_status="pending")
    session.add(v); session.commit()
    with pytest.raises(PublishNotReady):
        create_dispatch(session, acc, v, client=_FakeClient(), caption="gm")


def test_create_dispatch_requires_external_ref(session):
    acc = Account(platform="tiktok", handle="@x")   # no external_ref
    session.add(acc); session.commit()
    v = VideoAsset(account_id=acc.id, provider="fake", media_url="https://f/x.mp4",
                   dedup_key="k", status="ready", review_status="approved")
    session.add(v); session.commit()
    with pytest.raises(PublishNotReady):
        create_dispatch(session, acc, v, client=_FakeClient(), caption="gm")


def test_create_dispatch_publishes_and_records(session):
    acc, v = _approved_asset(session)
    client = _FakeClient()
    d = create_dispatch(session, acc, v, client=client, caption="gm airdrop szn")
    # payload built correctly: media = asset url, item targets the AiToEarn accountId + mapped platform
    assert client.published["items"][0]["accountId"] == "ae_1"
    assert client.published["items"][0]["platform"] == "tiktok"
    assert client.published["content"]["media"][0]["url"] == "https://f/x.mp4"
    # dispatch recorded
    assert d.aitoearn_flow_id == "f1" and d.aitoearn_task_id == "t1"
    assert d.status == "queued"          # WaitingForPublish -> queued
    assert d.media_urls == ["https://f/x.mp4"] and d.caption == "gm airdrop szn"


def test_refresh_dispatch_updates_work_id_and_status(session):
    acc, v = _approved_asset(session)
    client = _FakeClient()
    d = create_dispatch(session, acc, v, client=client, caption="x")
    refreshed = refresh_dispatch(session, d, client=client)
    assert refreshed.platform_work_id == "w9"
    assert refreshed.status == "published"    # Published -> published


def test_refresh_dispatch_empty_tasks_does_not_clobber(session):
    acc, v = _approved_asset(session)
    client = _FakeClient()
    d = create_dispatch(session, acc, v, client=client, caption="x")
    d.status = "published"; d.platform_work_id = "w9"; session.commit()
    class _EmptyClient:
        def flow_status(self, fid): return {"tasks": []}
    refresh_dispatch(session, d, client=_EmptyClient())
    assert d.status == "published" and d.platform_work_id == "w9"   # unchanged


def test_create_dispatch_refuses_double_publish(session):
    acc, v = _approved_asset(session)
    client = _FakeClient()
    create_dispatch(session, acc, v, client=client, caption="x")
    with pytest.raises(PublishNotReady):
        create_dispatch(session, acc, v, client=client, caption="x again")
