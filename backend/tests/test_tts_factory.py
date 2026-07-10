from __future__ import annotations

from types import SimpleNamespace

from app.video.tts.factory import resolve_tts_provider
from app.video.tts.fake import FakeTTSProvider


def _settings(**kw):
    base = dict(tts_provider="auto", tts_model="", tts_voice="alloy",
                tts_base_url=None, tts_api_key=None,
                anthropic_base_url="https://relay", anthropic_api_key="sk-x",
                video_output_dir="./data/videos")
    base.update(kw)
    return SimpleNamespace(**base)


def test_explicit_fake():
    p = resolve_tts_provider(_settings(tts_provider="fake"))
    assert isinstance(p, FakeTTSProvider)


def test_auto_picks_openai_when_model_and_key_present():
    from app.video.tts.openai import OpenAITTSProvider
    p = resolve_tts_provider(_settings(tts_provider="auto", tts_model="tts-1"))
    assert isinstance(p, OpenAITTSProvider)
    assert p._model == "tts-1" and p._base == "https://relay" and p._key == "sk-x"


def test_openai_uses_dedicated_base_key_over_anthropic():
    from app.video.tts.openai import OpenAITTSProvider
    p = resolve_tts_provider(_settings(tts_provider="openai", tts_model="tts-1",
                                       tts_base_url="https://tts", tts_api_key="sk-tts"))
    assert isinstance(p, OpenAITTSProvider) and p._base == "https://tts" and p._key == "sk-tts"


def test_openai_choice_without_model_falls_back_to_fake():
    p = resolve_tts_provider(_settings(tts_provider="openai", tts_model=""))
    assert isinstance(p, FakeTTSProvider)


def test_explicit_say_when_say_missing_falls_back_to_fake(monkeypatch):
    import app.video.tts.factory as fac
    monkeypatch.setattr(fac.shutil, "which", lambda name: None)
    p = resolve_tts_provider(_settings(tts_provider="say"))
    assert isinstance(p, FakeTTSProvider)
