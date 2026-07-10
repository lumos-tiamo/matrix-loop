"""TDD: config + factory gating for seedance vs fake provider."""
from __future__ import annotations

import pytest


def test_factory_returns_fake_by_default(monkeypatch):
    from app.config import settings
    from app.video.factory import resolve_video_provider
    from app.video.fake import FakeVideoProvider

    monkeypatch.setattr(settings, "video_provider", "fake", raising=False)
    p = resolve_video_provider()
    assert isinstance(p, FakeVideoProvider)
    assert p.name == "fake"


def test_factory_returns_seedance_when_configured(monkeypatch):
    from app.config import settings
    from app.video.factory import resolve_video_provider
    from app.video.seedance import SeedanceVideoProvider

    monkeypatch.setattr(settings, "video_provider", "seedance", raising=False)
    p = resolve_video_provider()
    assert isinstance(p, SeedanceVideoProvider)
    assert p.name == "seedance"


def test_resolve_returns_aitoearn_when_configured(monkeypatch):
    from app.config import settings
    from app.video.aitoearn import AiToEarnVideoProvider
    monkeypatch.setattr(settings, "video_provider", "aitoearn", raising=False)
    monkeypatch.setattr(settings, "aitoearn_ai_base_url", "http://h/api/ai", raising=False)
    monkeypatch.setattr(settings, "aitoearn_api_key", "k", raising=False)
    from app.video.factory import resolve_video_provider
    assert isinstance(resolve_video_provider(), AiToEarnVideoProvider)


def test_factory_falls_back_to_fake_on_construction_error(monkeypatch):
    """A misconfigured provider must never crash the loop — fall back to fake."""
    from app.config import settings
    from app.video.factory import resolve_video_provider
    from app.video.fake import FakeVideoProvider

    monkeypatch.setattr(settings, "video_provider", "seedance", raising=False)
    # Force the SeedanceVideoProvider constructor to raise
    import app.video.seedance as seedance_mod
    original_cls = seedance_mod.SeedanceVideoProvider

    class BrokenSeedance:
        def __init__(self, **kwargs):
            raise RuntimeError("broken config")

    monkeypatch.setattr(seedance_mod, "SeedanceVideoProvider", BrokenSeedance)
    p = resolve_video_provider()
    assert isinstance(p, FakeVideoProvider)
    # restore
    monkeypatch.setattr(seedance_mod, "SeedanceVideoProvider", original_cls)


def test_factory_returns_faceless_when_configured(monkeypatch, tmp_path):
    from app.config import settings
    from app.video.factory import resolve_video_provider
    from app.video.faceless import FacelessVideoProvider
    from app.video.fake import FakeVideoProvider

    monkeypatch.setattr(settings, "video_provider", "faceless", raising=False)
    monkeypatch.setattr(settings, "faceless_visual", "fake", raising=False)
    monkeypatch.setattr(settings, "tts_provider", "fake", raising=False)
    monkeypatch.setattr(settings, "video_output_dir", str(tmp_path), raising=False)
    p = resolve_video_provider()
    assert isinstance(p, FacelessVideoProvider)
    assert p.name == "faceless"
    # inner visual is a plain clip provider, never another faceless (no recursion)
    assert isinstance(p._visual, FakeVideoProvider)


def test_faceless_inner_visual_never_faceless(monkeypatch, tmp_path):
    """faceless_visual must resolve to a clip provider, even if set to 'faceless'."""
    from app.config import settings
    from app.video.factory import resolve_video_provider
    from app.video.faceless import FacelessVideoProvider
    from app.video.fake import FakeVideoProvider

    monkeypatch.setattr(settings, "video_provider", "faceless", raising=False)
    monkeypatch.setattr(settings, "faceless_visual", "faceless", raising=False)  # nonsense on purpose
    monkeypatch.setattr(settings, "tts_provider", "fake", raising=False)
    monkeypatch.setattr(settings, "video_output_dir", str(tmp_path), raising=False)
    p = resolve_video_provider()
    assert isinstance(p, FacelessVideoProvider)
    assert isinstance(p._visual, FakeVideoProvider)  # fell through to fake, no recursion
