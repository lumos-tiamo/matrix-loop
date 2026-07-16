import pytest

from app.analysis.fallback_client import FallbackLLMClient, _should_fallback


class _Stub:
    def __init__(self, *, reply=None, raise_exc=None):
        self.reply, self.raise_exc, self.calls = reply, raise_exc, 0
        self.last_usage = {"input": 1, "output": 2}

    def complete(self, *, system, prompt):
        self.calls += 1
        if self.raise_exc:
            raise self.raise_exc
        return self.reply


def test_uses_primary_when_it_works():
    p, s = _Stub(reply="from-agens"), _Stub(reply="from-newapi")
    fb = FallbackLLMClient(p, s)
    assert fb.complete(system="x", prompt="y") == "from-agens"
    assert fb.last_provider == "agens" and s.calls == 0


def test_falls_back_on_quota():
    p = _Stub(raise_exc=RuntimeError("insufficient_quota: daily free limit reached"))
    s = _Stub(reply="from-newapi")
    fb = FallbackLLMClient(p, s)
    assert fb.complete(system="x", prompt="y") == "from-newapi"
    assert fb.last_provider == "newapi" and p.calls == 1 and s.calls == 1


def test_reraises_non_quota_errors():
    p = _Stub(raise_exc=ValueError("malformed prompt"))
    s = _Stub(reply="unused")
    fb = FallbackLLMClient(p, s)
    with pytest.raises(ValueError):
        fb.complete(system="x", prompt="y")
    assert s.calls == 0   # a real bug should surface, not silently hit the paid relay


@pytest.mark.parametrize("msg", [
    "Error code: 429 Too Many Requests", "insufficient balance", "quota exhausted",
    "401 Unauthorized", "rate limit exceeded", "payment required",
])
def test_fallback_markers(msg):
    assert _should_fallback(RuntimeError(msg))


def test_status_code_attr_triggers_fallback():
    exc = RuntimeError("nope")
    exc.status_code = 429
    assert _should_fallback(exc)


def test_non_quota_message_does_not_fallback():
    assert not _should_fallback(RuntimeError("connection reset by peer"))


def test_factory_wires_agens_first_then_newapi(monkeypatch):
    from app.config import settings
    from app.analysis import factory
    monkeypatch.setattr(settings, "anthropic_api_key", "nk", raising=False)
    monkeypatch.setattr(settings, "agens_api_key", "ak", raising=False)
    monkeypatch.setattr(settings, "agens_base_url", "https://agens.example/v1", raising=False)
    monkeypatch.setattr(settings, "agens_protocol", "openai", raising=False)
    monkeypatch.setattr(settings, "prefer_agens", True, raising=False)
    # don't construct the real anthropic SDK
    monkeypatch.setattr("app.analysis.claude_client.ClaudeClient.__init__",
                        lambda self, *a, **k: setattr(self, "last_usage", None))
    client = factory.resolve_llm_client()
    assert isinstance(client, FallbackLLMClient)


def test_factory_agens_off_without_base_url(monkeypatch):
    from app.config import settings
    from app.analysis import factory
    monkeypatch.setattr(settings, "anthropic_api_key", "nk", raising=False)
    monkeypatch.setattr(settings, "agens_api_key", "ak", raising=False)
    monkeypatch.setattr(settings, "agens_base_url", None, raising=False)
    monkeypatch.setattr("app.analysis.claude_client.ClaudeClient.__init__",
                        lambda self, *a, **k: setattr(self, "last_usage", None))
    client = factory.resolve_llm_client()
    assert not isinstance(client, FallbackLLMClient)   # falls back to plain newapi client
