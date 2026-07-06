import json

import pytest

from app.models import Account, ContentItem
from app.analysis.llm import analyze_positioning, AnalysisResult


class FakeLLMClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, *, system: str, prompt: str) -> str:
        self.calls.append({"system": system, "prompt": prompt})
        if not self.responses:
            raise AssertionError("FakeLLMClient exhausted: no more canned responses")
        return self.responses.pop(0)


def _account():
    return Account(platform="xiaohongshu", handle="@a1", positioning="美妆")


def _content():
    return [ContentItem(account_id=1, views=100, topic="beauty"),
            ContentItem(account_id=1, views=200, topic="beauty,skincare")]


VALID = json.dumps({
    "positioning_clarity": 78,
    "positioning_label": "平价美妆测评",
    "content_direction": "聚焦百元内产品横评",
    "suggested_topics": ["5款百元粉底横评", "学生党护肤"],
})


def test_analyze_positioning_parses_valid_json():
    client = FakeLLMClient([VALID])
    result = analyze_positioning(_account(), _content(), client)
    assert isinstance(result, AnalysisResult)
    assert result.positioning_label == "平价美妆测评"
    assert result.suggested_topics == ["5款百元粉底横评", "学生党护肤"]


def test_prompt_includes_handle_and_topics():
    client = FakeLLMClient([VALID])
    analyze_positioning(_account(), _content(), client)
    prompt = client.calls[0]["prompt"]
    assert "@a1" in prompt
    assert "beauty" in prompt


def test_analyze_positioning_strips_code_fences():
    fenced = "```json\n" + VALID + "\n```"
    client = FakeLLMClient([fenced])
    result = analyze_positioning(_account(), _content(), client)
    assert result.positioning_clarity == 78.0


def test_analyze_positioning_retries_once_then_succeeds():
    client = FakeLLMClient(["not json at all", VALID])
    result = analyze_positioning(_account(), _content(), client)
    assert result.positioning_label == "平价美妆测评"
    assert len(client.calls) == 2  # retried once


def test_analyze_positioning_raises_after_two_failures():
    client = FakeLLMClient(["nope", "still nope"])
    with pytest.raises(ValueError):
        analyze_positioning(_account(), _content(), client)
    assert len(client.calls) == 2


def test_analyze_positioning_prose_brace_before_json_no_retry():
    """A brace in prose BEFORE the JSON object must not corrupt extraction (fix #1)."""
    response = "Note {see below}: " + VALID
    client = FakeLLMClient([response])
    result = analyze_positioning(_account(), _content(), client)
    assert result.positioning_label == "平价美妆测评"
    assert len(client.calls) == 1  # parsed first time, no retry
