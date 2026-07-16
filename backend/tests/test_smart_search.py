from app.analysis import smart_search
from app.analysis.smart_search import SearchHit
from app.models import Trend


def test_router_persists_and_dedupes(session):
    def fake_source(query, limit):
        return [SearchHit(source="fake", title="空投黄金第一课", url="http://x", engagement=999),
                SearchHit(source="fake", title="RWA 是什么", engagement=100)]
    smart_search.register_source("fake", fake_source)
    try:
        r1 = smart_search.smart_search(session, "web3", sources=["fake"], distill=False)
        assert r1["found"] == 2 and r1["persisted"] == 2
        assert session.query(Trend).count() == 2
        # second run: same titles -> all skipped as duplicates
        r2 = smart_search.smart_search(session, "web3", sources=["fake"], distill=False)
        assert r2["persisted"] == 0 and r2["skipped_duplicates"] == 2
    finally:
        smart_search._REGISTRY.pop("fake", None)


def test_unknown_source_is_skipped_not_fatal(session):
    r = smart_search.smart_search(session, "q", sources=["does-not-exist"], distill=False)
    assert r["found"] == 0 and r["persisted"] == 0


def test_failing_source_is_isolated(session):
    def boom(query, limit):
        raise RuntimeError("network down")
    smart_search.register_source("boom", boom)
    try:
        r = smart_search.smart_search(session, "q", sources=["boom"], distill=False)
        assert r["persisted"] == 0  # did not raise
    finally:
        smart_search._REGISTRY.pop("boom", None)


def test_openclaw_source_registered_and_noop_without_config(session, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "openclaw_base_url", "", raising=False)
    assert "openclaw" in smart_search.available_sources()
    assert smart_search._openclaw_source("q", 5) == []
