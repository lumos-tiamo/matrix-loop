import json

from app.models import Account, ContentItem, AudienceSegment
from app.flow.classify import classify_audience


class FakeLLMClient:
    def __init__(self, response): self.response = response; self.calls = []
    def complete(self, *, system, prompt): self.calls.append(prompt); return self.response


def test_classify_audience_returns_matching_labels():
    acc = Account(platform="twitter", handle="@a", positioning="crypto macro")
    content = [ContentItem(account_id=1, topic="bitcoin"), ContentItem(account_id=1, topic="defi")]
    client = FakeLLMClient(json.dumps({"segments": ["crypto", "海外投资者"]}))
    labels = classify_audience(acc, content, client, ["crypto", "海外投资者", "宝妈"])
    assert labels == ["crypto", "海外投资者"]
    assert "crypto" in client.calls[0]  # candidate labels in prompt


def test_classify_audience_filters_unknown_labels():
    acc = Account(platform="x", handle="@a")
    client_ = type("C", (), {"complete": lambda self, *, system, prompt: json.dumps({"segments": ["crypto", "bogus"]})})()
    labels = classify_audience(acc, [], client_, ["crypto", "海外投资者"])
    assert labels == ["crypto"]      # 'bogus' not in candidate set -> dropped
