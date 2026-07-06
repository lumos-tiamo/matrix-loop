import sys
import types

import pytest

from app.analysis.claude_client import ClaudeClient


def test_missing_api_key_raises():
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        ClaudeClient(api_key=None)


def test_complete_builds_request_and_returns_text(monkeypatch):
    captured = {}

    class _TextBlock:
        type = "text"
        def __init__(self, text): self.text = text

    class _Message:
        content = [_TextBlock("hello world")]

    class _Messages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Message()

    class _FakeAnthropic:
        def __init__(self, **kwargs):
            captured["init"] = kwargs
            self.messages = _Messages()

    fake_module = types.SimpleNamespace(Anthropic=_FakeAnthropic)
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    client = ClaudeClient(api_key="sk-test", model="claude-sonnet-4-6")
    out = client.complete(system="SYS", prompt="PROMPT")

    assert out == "hello world"
    assert captured["model"] == "claude-sonnet-4-6"
    assert captured["system"] == "SYS"
    assert captured["messages"] == [{"role": "user", "content": "PROMPT"}]
    assert captured["init"]["api_key"] == "sk-test"
