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
        "Return ONLY JSON: {\"cover\":\"<=14-word hook\",\"slides\":[5 slides],\"cta\":\"<short>\"}\n"
        "Each slide is ONE of these (prefer data-viz over statement; MIX kinds):\n"
        "{\"kind\":\"stat\",\"big\":\"$90.7B\",\"delta\":\"↑ tops 2025\",\"label\":\"what it is\",\"caption\":\"1 line\"}\n"
        "{\"kind\":\"compare\",\"title\":\"X vs Y\",\"items\":[[\"label\",90.7,\"$90.7B\"],[\"label\",84.6,\"$84.6B\"]],\"caption\":\"..\"}\n"
        "{\"kind\":\"donut\",\"pct\":90,\"label\":\"what the % means\",\"caption\":\"..\"}\n"
        "{\"kind\":\"rank\",\"title\":\"leaderboard\",\"items\":[[\"label\",5.5,\"5.5%\"],[\"label\",3.6,\"3.6%\"]],\"caption\":\"..\"}\n"
        "{\"kind\":\"chart\",\"coin\":\"bitcoin\",\"title\":\"..\",\"caption\":\"..\"}\n"
        "{\"kind\":\"statement\",\"title\":\"bold claim\",\"caption\":\"..\"}\n"
        f"{chart_hint}\n"
        "RULES: use ONLY real numbers present in the topic — never invent values, prices, or %s. In items, the "
        "number is the bar length and display is the shown text. Compliance: NFA, no return promises. Output JSON only."
    )
    for _ in range(3):   # relay routing is flaky -> retry
        try:
            raw = llm.complete(system="You are a precise data-infographic designer. Output only valid JSON.", prompt=prompt)
            m = _re.search(r"\{.*\}", raw, _re.S)
            spec = json.loads(m.group(0)) if m else None
            if spec and spec.get("slides"):
                return spec
        except Exception as e:  # noqa: BLE001
            print(f"  spec retry ({brand}): {e.__class__.__name__}")
    return None


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
            if spec:
                pngs = GC.render_spec(spec, brand, is_cjk, out_dir)
                script = spec.get("cover", topic)
            else:   # fallback: prose script -> auto slides
                try:
                    text = generate_script(topic, brief, llm, trends=trend_prompt_block(s, brief.sub_niches))
                except Exception as e:  # noqa: BLE001
                    print(f"  {a.handle}: script err {e}"); continue
                pkg = build_pkg_from_script(text, brand, brief.language); pkg["id"] = f"{brand}-day"
                pngs = GC.render_pkg(pkg, out_dir, "bitcoin" if brand == "CC" else None)
                script = text
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
