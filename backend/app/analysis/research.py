"""B-layer research, IN the backend — so matrix-loop refreshes verified hot topics WITHOUT Claude.

Uses the LLM relay's native web_search server tool (Anthropic web_search_20250305, confirmed
supported via newapi) to research + verify current hot topics per account niche, then ingests them
as Trends (which run_daily_cycle --from-trends turns into data-rich videos). This replaces the
Claude Workflow B-layer for the autonomous path; same idea (live web + real numbers + sources).
"""
from __future__ import annotations

import json
import re
import urllib.request

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Trend

# account_id -> (niche matching sub_niches, search scope)
NICHE = {
    9:  ("airdrops", "crypto airdrops, points/farming programs, TGEs, token distributions, snapshot dates, eligibility"),
    10: ("macro", "BTC/ETH & major price action, liquidations, funding rates, ETF flows, notable on-chain moves"),
    11: ("RWA", "stablecoin yield, RWA, tokenized US treasuries & gold, real DeFi APYs, T-bill rates"),
    8:  ("crypto科普", "Web3/crypto for a Taiwan 繁中 audience: regulation/VASP law, scam-safety, gold-on-chain, AI x crypto"),
}
BANNED = "gold token mktcap $7.1B / +300%, gold price $4,768, Robinhood 70k agent accounts, BUIDL $25B, sUSDe 10-15%, 'Fed cutting rates' (it is a HIKING environment)"


def _web_search(prompt: str, *, max_uses: int = 5, max_tokens: int = 1800, retries: int = 3) -> str:
    """Web-search-grounded LLM call. The newapi relay routes randomly and some upstreams reject the
    web_search server tool (400) — so retry a few times (re-routes to a supporting upstream)."""
    body = {
        "model": settings.llm_model or "claude-sonnet-4-6",
        "max_tokens": max_tokens,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}],
        "messages": [{"role": "user", "content": prompt}],
    }
    data = json.dumps(body).encode()
    last = None
    for _ in range(retries):
        req = urllib.request.Request(
            settings.anthropic_base_url.rstrip("/") + "/v1/messages", data=data, method="POST",
            headers={"content-type": "application/json", "x-api-key": settings.anthropic_api_key,
                     "anthropic-version": "2023-06-01"},
        )
        try:
            with urllib.request.urlopen(req, timeout=150) as r:
                out = json.loads(r.read().decode())
            return " ".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
        except Exception as exc:  # noqa: BLE001 - retry random-routing 400s
            last = exc
    raise RuntimeError(f"web_search unavailable after {retries} tries: {last}")


def _llm_only(prompt: str) -> str:
    """Fallback when the relay's web_search is unavailable: plain LLM (no live data, knowledge-based)."""
    from app.analysis.factory import resolve_llm_client
    client = resolve_llm_client()
    return client.complete(system="You are a precise crypto research analyst.", prompt=prompt) if client else ""


def research_niche(niche: str, scope: str, n: int = 4) -> list[dict]:
    """Return up to n verified topics: [{distilled_topic(with real number), source_url, title, confidence}]."""
    prompt = (
        f"Use web search to find the {n} SHARPEST, most CURRENT (prefer the last ~2 weeks), VERIFIABLE "
        f"hot topics in: {scope}.\n"
        f"For EACH: write a one-sentence 'distilled_topic' that BAKES IN a real specific number/date, and "
        f"give the source_url you actually found it at. The source must explicitly support the number — if "
        f"you cannot confirm it, DROP the item. Ignore known-false claims: {BANNED}.\n"
        f"Return ONLY a JSON array, no prose:\n"
        f'[{{"distilled_topic":"...real number...","source_url":"https://...","title":"...","confidence":0.0-1.0}}]'
    )
    try:
        txt = _web_search(prompt)
    except Exception:  # noqa: BLE001 - relay web_search flaky -> knowledge-based fallback (no fabricated numbers)
        txt = _llm_only(prompt + "\nWeb search is unavailable; use only facts you are confident are real, "
                        "keep numbers only if certain, otherwise stay specific but qualitative. Set source_url to \"\".")
    m = re.search(r"\[.*\]", txt, re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return []
    out = []
    for x in arr:
        if isinstance(x, dict) and x.get("distilled_topic"):
            out.append(x)
    return out[:n]


def research_and_ingest(session: Session, *, per_niche: int = 4) -> dict:
    """Research all 4 niches via web search, ingest fresh verified topics as Trends. Idempotent on
    (source,title). Returns {niche: count}."""
    result = {}
    for aid, (niche, scope) in NICHE.items():
        try:
            items = research_niche(niche, scope, per_niche)
        except Exception as exc:  # noqa: BLE001
            result[niche] = f"error: {exc.__class__.__name__}"
            continue
        added = 0
        for it in items:
            title = (it.get("title") or it["distilled_topic"])[:200]
            exists = session.scalar(select(Trend).where(Trend.source == "web", Trend.title == title))
            if exists:
                continue
            session.add(Trend(
                source="web", title=title, url=it.get("source_url"), niche=niche,
                distilled_topic=it["distilled_topic"][:600],
                score=round(float(it.get("confidence", 0.8)) * 100, 1),
            ))
            added += 1
        session.commit()
        result[niche] = added
    return result
