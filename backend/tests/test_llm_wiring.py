import json
from datetime import datetime, timezone

import app.analysis.factory as factory_mod
from app.models import Account, Snapshot, ContentItem


class FakeLLMClient:
    def __init__(self, response): self.response = response
    def complete(self, *, system, prompt): return self.response
    last_usage = {"input": 10, "output": 20}


_LLM_JSON = json.dumps({
    "positioning_clarity": 88,
    "positioning_label": "平价美妆测评",
    "content_direction": "聚焦百元内产品横评",
    "suggested_topics": ["5款百元粉底横评"],
})


def _seed(session, weights=None):
    acc = Account(platform="xiaohongshu", handle="@a1",
                  objective_weights=weights or {"growth": 0.0, "engagement": 0.0, "commercial": 0.0, "positioning": 1.0})
    session.add(acc); session.commit()
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=100000),
        ContentItem(account_id=acc.id, views=100, topic="beauty"),
    ])
    session.commit()
    return acc


def test_resolve_returns_none_without_key(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "anthropic_api_key", None, raising=False)
    assert factory_mod.resolve_llm_client() is None


def test_resolve_returns_client_with_key(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key", raising=False)
    monkeypatch.setattr(settings, "anthropic_base_url", "https://example.test", raising=False)
    client = factory_mod.resolve_llm_client()
    assert client is not None and hasattr(client, "complete")


def test_trigger_loop_uses_llm_when_configured(client, session, monkeypatch):
    acc = _seed(session)
    monkeypatch.setattr("app.api.routes.resolve_llm_client", lambda: FakeLLMClient(_LLM_JSON))
    resp = client.post(f"/accounts/{acc.id}/loop")
    assert resp.status_code == 200
    body = resp.json()
    # positioning weight 1.0 -> composite == LLM clarity 88; diagnosis carries the LLM label
    assert body["evaluation"]["composite_score"] == 88.0
    assert "平价美妆测评" in body["diagnosis"]


def test_trigger_loop_falls_back_to_deterministic(client, session, monkeypatch):
    acc = _seed(session)
    monkeypatch.setattr("app.api.routes.resolve_llm_client", lambda: None)
    resp = client.post(f"/accounts/{acc.id}/loop")
    assert resp.status_code == 200
    # deterministic path: single-topic content -> proxy clarity 100 -> composite 100
    assert resp.json()["evaluation"]["composite_score"] == 100.0


def test_run_batch_uses_injected_llm(session):
    from app.scheduler.batch import run_batch
    _seed(session)
    report = run_batch(session, sync=False, llm_client=FakeLLMClient(_LLM_JSON))
    assert report.looped == 1
    assert report.total_tokens == 30  # 10 + 20 from FakeLLMClient.last_usage
