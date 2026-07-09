from datetime import datetime, timezone

from app.models import Account, ContentItem, Draft, LoopRun, PublishDispatch, VideoAsset
from app.publish.analytics import refresh_published_analytics


class _FakeClient:
    def __init__(self, payload): self._p = payload; self.calls = []
    def work_analytics(self, platform, work_id, account_id, since=None, until=None):
        self.calls.append((platform, work_id, account_id)); return self._p


def _published(session):
    acc = Account(platform="tiktok", handle="@x", external_ref="ae_1"); session.add(acc); session.commit()
    lr = LoopRun(account_id=acc.id); session.add(lr); session.commit()
    d = Draft(loop_run_id=lr.id, kind="script", content="crypto airdrop guide script", review_status="adopted")
    session.add(d); session.commit()
    v = VideoAsset(account_id=acc.id, script_draft_id=d.id, provider="fake", dedup_key="k", review_status="approved")
    session.add(v); session.commit()
    disp = PublishDispatch(account_id=acc.id, video_asset_id=v.id, platform_work_id="w9", status="published")
    session.add(disp); session.commit()
    return acc, v, d, disp


def test_refresh_backfills_attributed_content_item(session):
    acc, v, d, disp = _published(session)
    client = _FakeClient({"metrics": {"viewCount": 12000, "likeCount": 800, "commentCount": 45},
                          "work": {"publishedAt": "2026-07-08T10:00:00+00:00"}})
    report = refresh_published_analytics(session, client=client)
    assert report["refreshed"] == 1
    assert client.calls == [("tiktok", "w9", "ae_1")]
    ci = session.query(ContentItem).filter_by(account_id=acc.id, platform_post_id="w9").one()
    assert ci.views == 12000 and ci.likes == 800 and ci.comments == 45
    assert ci.video_asset_id == v.id and ci.draft_id == d.id        # attributed
    assert ci.topic and "crypto airdrop" in ci.topic                # topic snippet from script


def test_refresh_is_idempotent(session):
    acc, v, d, disp = _published(session)
    client = _FakeClient({"metrics": {"viewCount": 5, "likeCount": 1, "commentCount": 0}, "work": {}})
    refresh_published_analytics(session, client=client)
    refresh_published_analytics(session, client=client)
    assert session.query(ContentItem).filter_by(account_id=acc.id, platform_post_id="w9").count() == 1  # no dup


def test_refresh_skips_dispatches_without_work_id(session):
    acc = Account(platform="tiktok", handle="@y", external_ref="ae_2"); session.add(acc); session.commit()
    session.add(PublishDispatch(account_id=acc.id, status="queued")); session.commit()  # no platform_work_id
    report = refresh_published_analytics(session, client=_FakeClient({}))
    assert report["refreshed"] == 0
