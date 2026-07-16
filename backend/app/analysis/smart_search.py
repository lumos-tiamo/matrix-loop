"""Smart Search — a source-routing intel gatherer, borrowed from xiaobei's smart-search skill.

xiaobei runs its searches through an openclaw browser over 18 key-free sources. matrix-loop is a
code service, so here Smart Search is a *router over pluggable source fetchers*: each source is a
callable(query, limit) -> list[SearchHit]. Results are normalized, optionally distilled by the
LLM into a "拍什么" angle, and persisted as Trend rows (dedup on source+title) so they flow into
the existing 选题池 / trend_prompt_block. The openclaw HTTP source ships here; more can register.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Trend

logger = logging.getLogger(__name__)


@dataclass
class SearchHit:
    source: str
    title: str
    url: str | None = None
    engagement: int | None = None
    extra: dict = field(default_factory=dict)


# a source fetcher: (query, limit) -> list[SearchHit]
SourceFn = Callable[[str, int], list]

# process-wide source registry; register_source() adds fetchers (openclaw, future connectors)
_REGISTRY: dict[str, SourceFn] = {}


def register_source(name: str, fn: SourceFn) -> None:
    _REGISTRY[name] = fn


def available_sources() -> list[str]:
    return sorted(_REGISTRY)


def _openclaw_source(query: str, limit: int) -> list[SearchHit]:
    """Search via the user's openclaw gateway (key-free, browser-backed). No-op if unconfigured
    — Smart Search must never take down the loop just because openclaw is offline."""
    from app.config import settings
    base = (settings.openclaw_base_url or "").rstrip("/")
    if not base:
        return []
    import httpx
    try:
        headers = {"Authorization": f"Bearer {settings.openclaw_token}"} if settings.openclaw_token else {}
        resp = httpx.post(f"{base}/smart-search",
                          json={"query": query, "limit": limit}, headers=headers, timeout=30)
        resp.raise_for_status()
        hits = resp.json().get("results", [])
    except Exception as exc:  # noqa: BLE001 - external source failures are non-fatal
        logger.warning("openclaw smart-search failed for %r: %s", query, exc)
        return []
    return [SearchHit(source=h.get("source", "openclaw"), title=h.get("title", ""),
                      url=h.get("url"), engagement=h.get("engagement")) for h in hits if h.get("title")]


register_source("openclaw", _openclaw_source)


def _distill(hit: SearchHit, niche: str | None, client) -> str | None:
    if client is None:
        return None
    from app.analysis.llm import _extract_json
    import json
    try:
        raw = client.complete(
            system="你把一条热点提炼成一个可直接开拍的短视频选题角度,一句话,中文,面向Web3出海观众。",
            prompt=f"热点: {hit.title}\n领域: {niche or '-'}\n输出 JSON: {{\"topic\": \"...\"}}")
        return str(json.loads(_extract_json(raw)).get("topic", ""))[:300] or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("smart-search distill failed: %s", exc)
        return None


def smart_search(session: Session, query: str, *, sources: list[str] | None = None,
                 niche: str | None = None, limit: int = 8, client=None,
                 distill: bool = True) -> dict:
    """Route `query` to the selected sources, persist fresh hits as Trend rows (deduped on
    source+title), and return a summary. Returns counts + the persisted trend ids."""
    names = sources or available_sources()
    hits: list[SearchHit] = []
    for name in names:
        fn = _REGISTRY.get(name)
        if fn is None:
            logger.warning("smart-search: unknown source %r (have %s)", name, available_sources())
            continue
        try:
            hits.extend(fn(query, limit) or [])
        except Exception as exc:  # noqa: BLE001 - isolate per-source failures
            logger.warning("smart-search source %r failed: %s", name, exc)

    persisted: list[int] = []
    skipped = 0
    for hit in hits:
        title = (hit.title or "").strip()
        if not title:
            continue
        exists = session.scalar(
            select(Trend).where(Trend.source == hit.source, Trend.title == title))
        if exists is not None:
            skipped += 1
            continue
        distilled = _distill(hit, niche, client) if distill else None
        row = Trend(source=hit.source[:24], title=title, url=hit.url, niche=niche,
                    engagement=hit.engagement, distilled_topic=distilled,
                    score=float(hit.engagement or 0))
        session.add(row)
        session.flush()
        persisted.append(row.id)
    session.commit()
    return {"query": query, "sources": names, "found": len(hits),
            "persisted": len(persisted), "skipped_duplicates": skipped, "trend_ids": persisted}
