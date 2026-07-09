from app.video.base import VideoResult
from app.video.fake import FakeVideoProvider
from app.video.factory import resolve_video_provider


def test_fake_provider_is_deterministic_by_script():
    p = FakeVideoProvider()
    r1 = p.generate(script="hello world", brief=None, params={})
    r2 = p.generate(script="hello world", brief=None, params={})
    r3 = p.generate(script="different", brief=None, params={})
    assert isinstance(r1, VideoResult)
    assert r1.provider == "fake" and r1.cost > 0 and r1.duration > 0
    assert r1.media_url == r2.media_url and r1.dedup_key == r2.dedup_key
    assert r1.media_url != r3.media_url


def test_resolve_video_provider_defaults_to_fake():
    assert resolve_video_provider().name == "fake"
