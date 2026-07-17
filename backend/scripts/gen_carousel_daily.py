#!/usr/bin/env python3
"""Daily 图文 carousels — one real-data carousel per account from its top VERIFIED trend.
trend.distilled_topic -> generate_script (grounded) -> build_pkg_from_script -> gen_carousel.render_pkg
-> PNG slides in data/carousels/<BRAND>-<date>/ + meta.json. Real images only (no AI).

Run from backend/ with the venv python.  Flags: --only <account_id>
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND)
os.chdir(_BACKEND)
sys.path.insert(0, os.path.join(os.path.dirname(_BACKEND), "hyperframes-batch"))

from app.analysis.factory import resolve_llm_client  # noqa: E402
from app.analysis.script import generate_script  # noqa: E402
from app.analysis.trends import trend_prompt_block  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Account, ChannelBrief, Trend  # noqa: E402

import gen_carousel as GC  # noqa: E402
from produce2 import build_pkg_from_script  # noqa: E402

BRAND_OF = {8: "AU", 9: "AE", 10: "CC", 11: "QY"}
LAUNCH = "2026-07-20"


def _opt(flag):
    for i, a in enumerate(sys.argv[1:]):
        if a == flag and i + 1 < len(sys.argv[1:]):
            return sys.argv[1:][i + 1]
    return None


import re as _re


def _spec_from_trend(topic, brand, is_cjk, llm):
    """LLM -> structured infographic spec (real-number data-viz per slide). None on failure."""
    if not llm:
        return None
    lang = "用繁體中文" if is_cjk else "in English"
    chart_hint = "Include ONE {\"kind\":\"chart\",\"coin\":\"bitcoin|ethereum|solana\",...} slide." if brand == "CC" else ""
    prompt = (
        f"Design a 5-slide data infographic carousel {lang} for a crypto account, from this VERIFIED topic:\n{topic}\n\n"
        "Return ONLY JSON: {\"cover\":\"<=14-word hook\",\"cover_coin\":\"<CoinGecko id or ''>\",\"slides\":[5 slides],\"cta\":\"<short>\"}\n"
        "Each slide is ONE of these (prefer data-viz over statement; MIX kinds — vary the mix so carousels don't look alike):\n"
        "{\"kind\":\"stat\",\"big\":\"$90.7B\",\"delta\":\"↑ tops 2025\",\"label\":\"what it is\",\"coin\":\"<CoinGecko id or ''>\",\"caption\":\"1 line\"}\n"
        "{\"kind\":\"compare\",\"title\":\"X vs Y\",\"items\":[[\"Bitcoin\",90.7,\"$90.7B\",\"bitcoin\"],[\"Ethereum\",84.6,\"$84.6B\",\"ethereum\"]],\"caption\":\"..\"}\n"
        "{\"kind\":\"donut\",\"pct\":90,\"label\":\"what the % means\",\"caption\":\"..\"}\n"
        "{\"kind\":\"rank\",\"title\":\"leaderboard\",\"items\":[[\"Aave\",5.5,\"5.5%\",\"aave\"],[\"Sky\",3.6,\"3.6%\",\"\"]],\"caption\":\"..\"}\n"
        "{\"kind\":\"chart\",\"coin\":\"bitcoin\",\"title\":\"..\",\"caption\":\"..\"}\n"
        "{\"kind\":\"statement\",\"title\":\"bold claim\",\"caption\":\"..\"}\n"
        f"{chart_hint}\n"
        "CONTENT-SPECIFIC IMAGERY: set cover_coin to the topic's MAIN asset, and give each stat/compare/rank item that IS a "
        "listed crypto/token/gold its exact CoinGecko id (4th item element / stat.coin). Use ONLY ids you are SURE exist "
        "(bitcoin, ethereum, solana, pax-gold, tether-gold, usd-coin, aave, ethena, chainlink, ondo-finance, maker, ...). "
        "If unsure or it's an unlisted airdrop/protocol, use '' — NEVER guess an id.\n"
        "RULES: use ONLY real numbers present in the topic — never invent values, prices, or %s. In items, the "
        "number is the bar length and display is the shown text. Compliance: NFA, no return promises. Output JSON only."
    )
    for _ in range(3):   # relay routing is flaky -> retry
        try:
            raw = (llm.complete(system="You are a precise data-infographic designer. Output only valid JSON.", prompt=prompt) or "").strip()
            raw = _re.sub(r"```(?:json)?", "", raw)          # strip code fences
            m = _re.search(r"\{.*\}", raw, _re.S)
            blob = _re.sub(r",(\s*[}\]])", r"\1", m.group(0)) if m else ""   # kill trailing commas
            spec = json.loads(blob) if blob else None
            if spec and spec.get("slides"):
                return spec
        except Exception as e:  # noqa: BLE001
            print(f"  spec retry ({brand}): {e.__class__.__name__}")
    return None


def _fallback_spec(text, is_cjk):
    """No LLM spec -> still render via the account ARCHETYPE (not the old shared template).
    Turns the grounded script into cover + statement/stat slides so every account stays differentiated."""
    parts = [GC.clean_text(GC.drop_placeholders(p)) for p in _re.split(r"(?<=[.!?。!?])\s+", text or "")]
    parts = [p for p in parts if p and len(p) > 2]
    if not parts:
        return None
    slides, used_stat = [], False
    for p in parts[1:]:
        if len(slides) >= 5:
            break
        hn = GC.hero_number(p)
        if hn and (hn[0] or hn[2]) and not used_stat:
            used_stat = True
            slides.append({"kind": "stat", "big": GC._hero_num(hn), "label": p[:70], "caption": p[:120]})
        else:
            slides.append({"kind": "statement", "title": p[:80], "caption": ""})
    return {"cover": parts[0][:90], "cover_coin": "", "slides": slides or [{"kind": "statement", "title": parts[0][:80]}], "cta": ""}


def main():
    only = _opt("--only")
    today = date.today().isoformat()
    d = LAUNCH if today < LAUNCH else today
    s = SessionLocal()
    llm = resolve_llm_client()
    made = []
    try:
        accts = s.query(Account).order_by(Account.id).all()
        if only:
            accts = [a for a in accts if str(a.id) == str(only)]
        for a in accts:
            brand = BRAND_OF.get(a.id, "AE")
            brief = s.query(ChannelBrief).filter(ChannelBrief.account_id == a.id).first()
            if not brief:
                continue
            t = (s.query(Trend).filter(Trend.niche.in_(brief.sub_niches))
                 .order_by(Trend.captured_at.desc(), Trend.id.desc()).first())
            if not t:
                print(f"  {a.handle}: no trend, skip"); continue
            topic = t.distilled_topic or t.title
            is_cjk = (brief.language or "").startswith(("繁", "zh"))
            out_dir = os.path.join(GC.OUT_ROOT, f"{brand}-{d}")
            spec = _spec_from_trend(topic, brand, is_cjk, llm)
            if not spec:   # spec failed -> build a spec from the grounded script, STILL via the archetype skin
                try:
                    text = generate_script(topic, brief, llm, trends=trend_prompt_block(s, brief.sub_niches))
                    spec = _fallback_spec(text, is_cjk)
                    if spec:
                        print(f"  {a.handle}: spec fallback from script")
                except Exception as e:  # noqa: BLE001
                    print(f"  {a.handle}: script err {e}")
            if spec:
                pngs = GC.render_spec(spec, brand, is_cjk, out_dir)
                script = spec.get("cover", topic)
            else:   # last resort
                pkg = build_pkg_from_script(topic, brand, brief.language); pkg["id"] = f"{brand}-day"
                pngs = GC.render_pkg(pkg, out_dir, "bitcoin" if brand == "CC" else None)
                script = topic
            meta = {"account_id": a.id, "handle": a.handle, "brand": brand, "date": d,
                    "topic": topic[:200], "source": t.url, "source_score": t.score,
                    "script": script, "platform": a.platform, "slides": len(pngs),
                    "folder": f"{brand}-{d}"}
            json.dump(meta, open(os.path.join(out_dir, "meta.json"), "w"), ensure_ascii=False)
            made.append(meta)
            print(f"  ✓ {a.handle}: {len(pngs)} 图 -> {out_dir}")
    finally:
        s.close()
    print(f"CAROUSEL_DAILY: {len(made)} carousels")


if __name__ == "__main__":
    main()
