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
            try:
                text = generate_script(topic, brief, llm, trends=trend_prompt_block(s, brief.sub_niches))
            except Exception as e:  # noqa: BLE001
                print(f"  {a.handle}: script err {e}"); continue
            pkg = build_pkg_from_script(text, brand, brief.language)
            pkg["id"] = f"{brand}-day"
            out_dir = os.path.join(GC.OUT_ROOT, f"{brand}-{d}")
            coin = "bitcoin" if brand == "CC" else None
            pngs = GC.render_pkg(pkg, out_dir, coin)
            meta = {"account_id": a.id, "handle": a.handle, "brand": brand, "date": d,
                    "topic": topic[:200], "source": t.url, "source_score": t.score,
                    "script": text, "platform": a.platform, "slides": len(pngs),
                    "folder": f"{brand}-{d}"}
            json.dump(meta, open(os.path.join(out_dir, "meta.json"), "w"), ensure_ascii=False)
            made.append(meta)
            print(f"  ✓ {a.handle}: {len(pngs)} 图 -> {out_dir}")
    finally:
        s.close()
    print(f"CAROUSEL_DAILY: {len(made)} carousels")


if __name__ == "__main__":
    main()
