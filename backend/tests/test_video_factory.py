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
