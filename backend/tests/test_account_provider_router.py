from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.video.factory import make_account_provider_resolver


class _P:
    def __init__(self, name):
        self.name = name

    def generate(self, *, script, brief, params):
        raise AssertionError("not called in router tests")


def test_resolver_routes_avatar_handle(monkeypatch):
    from app.config import settings
    import app.video.factory as fac

    monkeypatch.setattr(settings, "avatar_handles", "askaurea, quiet.yield")
    # stub the underlying resolve so we don't build real providers
    monkeypatch.setattr(fac, "resolve_video_provider", lambda: _P("global"))
    # patch avatar build path: temporarily setting video_provider=avatar then resolving
    calls = {"n": 0}

    def fake_resolve():
        # avatar branch sets settings.video_provider='avatar' before calling
        return _P("avatar") if settings.video_provider == "avatar" else _P("global")

    monkeypatch.setattr(fac, "resolve_video_provider", fake_resolve)

    resolver = make_account_provider_resolver()
    aurea = SimpleNamespace(handle="@askaurea")
    x_acct = SimpleNamespace(handle="AirdropEdge")
    assert resolver(aurea).name == "avatar"        # matched (case/@ insensitive)
    assert resolver(x_acct).name == "global"        # not in avatar_handles


def test_resolver_caches_providers(monkeypatch):
    from app.config import settings
    import app.video.factory as fac

    monkeypatch.setattr(settings, "avatar_handles", "askaurea")
    builds = {"n": 0}

    def fake_resolve():
        builds["n"] += 1
        return _P("avatar" if settings.video_provider == "avatar" else "global")

    monkeypatch.setattr(fac, "resolve_video_provider", fake_resolve)
    resolver = make_account_provider_resolver()
    a = SimpleNamespace(handle="askaurea")
    b = SimpleNamespace(handle="other")
    resolver(a); resolver(a); resolver(b); resolver(b)
    assert builds["n"] == 2      # avatar built once + global built once, then cached


def test_resolver_restores_video_provider(monkeypatch):
    from app.config import settings
    import app.video.factory as fac

    monkeypatch.setattr(settings, "video_provider", "faceless")
    monkeypatch.setattr(settings, "avatar_handles", "askaurea")
    monkeypatch.setattr(fac, "resolve_video_provider",
                        lambda: _P("avatar" if settings.video_provider == "avatar" else "faceless"))
    resolver = make_account_provider_resolver()
    resolver(SimpleNamespace(handle="askaurea"))
    assert settings.video_provider == "faceless"     # restored after avatar build


def test_advance_account_accepts_resolver_callable(session):
    """The orchestrator must accept video=callable(account)->provider, routing per account."""
    from app.models import Account, ContentItem, Snapshot
    from app.orchestrator.engine import advance_account
    from datetime import datetime, timezone
    import json

    analysis = json.dumps({"positioning_clarity": 70, "positioning_label": "crypto",
                           "content_direction": "airdrops", "suggested_topics": ["a", "b"]})

    class _LLM:
        last_usage = {"input": 1, "output": 1}
        def complete(self, *, system, prompt): return analysis

    seen = {}

    class _Vid:
        def __init__(self, name): self.name = name
        def generate(self, *, script, brief, params):
            from app.video.base import VideoResult
            return VideoResult(media_url="https://cdn/x.mp4", duration=5, cost=1,
                               provider=self.name, dedup_key="d", metadata={})

    def resolver(account):
        seen["handle"] = account.handle
        return _Vid("avatar")

    a = Account(platform="tiktok", handle="@askaurea", autopilot=True, external_ref="ae_x",
                objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(a); session.commit()
    session.add_all([Snapshot(account_id=a.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100),
                     ContentItem(account_id=a.id, topic="airdrop", views=5000)])
    session.commit()

    rep = advance_account(session, a, llm=_LLM(), video=resolver, aitoearn=None, sync=False)
    assert seen["handle"] == "@askaurea"          # resolver was called with the account
    assert "video" in [e for e in rep.get("actions", [])] or rep["reached_step"] is not None
