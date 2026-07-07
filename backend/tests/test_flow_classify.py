import json

from app.models import Account, ContentItem, AudienceSegment, AccountSegment
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


def test_classify_endpoint_assigns_via_mocked_client(client, session, monkeypatch):
    # Setup: account + content + 2 segments
    acc = Account(platform="twitter", handle="@classify_test")
    session.add(acc); session.commit()
    session.add(ContentItem(account_id=acc.id, topic="bitcoin price action"))
    seg_crypto = AudienceSegment(label="crypto")
    seg_defi = AudienceSegment(label="defi")
    session.add_all([seg_crypto, seg_defi]); session.commit()

    # Fake ClaudeClient that always returns {"segments": ["crypto"]}
    class _FakeClient:
        def complete(self, *, system, prompt):
            return json.dumps({"segments": ["crypto"]})

    import app.api.routes as routes_mod
    monkeypatch.setattr(routes_mod, "ClaudeClient", lambda: _FakeClient())

    r = client.post(f"/accounts/{acc.id}/classify-audience")
    assert r.status_code == 200
    assert r.json()["segments"] == ["crypto"]

    rows = session.query(AccountSegment).filter_by(account_id=acc.id).all()
    assert len(rows) == 1
    assert rows[0].segment_id == seg_crypto.id
