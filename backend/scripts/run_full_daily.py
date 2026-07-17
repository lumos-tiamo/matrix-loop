#!/usr/bin/env python3
"""FULL autonomous daily — the ONE command that reproduces the whole data-rich daily effect
WITHOUT Claude: web research -> ingest Trends -> clear yesterday's daily -> generate --from-trends
-> Obsidian daily calendar. Used by the /schedule/run-full-daily endpoint, the daily launchd job,
and the ⚡ frontend button.

Run from backend/ with the venv python.  Flags: --rounds N (default 4), --keep (don't clear old daily).
"""
from __future__ import annotations

import os
import subprocess
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND)
os.chdir(_BACKEND)

from app.analysis.research import research_and_ingest  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import PublishPlan, VideoAsset  # noqa: E402

ROOT = os.path.dirname(_BACKEND)
PY = sys.executable


def _rounds():
    for i, a in enumerate(sys.argv[1:]):
        if a == "--rounds" and i + 1 < len(sys.argv[1:]):
            return sys.argv[1:][i + 1]
        if a.startswith("--rounds="):
            return a.split("=", 1)[1]
    return "4"


def _clear_old_daily():
    s = SessionLocal()
    try:
        n = 0
        for a in s.query(VideoAsset).all():
            if (a.dedup_key or "").startswith("batch-"):
                continue  # keep seed 16
            s.query(PublishPlan).filter(PublishPlan.video_asset_id == a.id).delete()
            if a.media_url:
                fp = os.path.join(_BACKEND, "data", "videos", os.path.basename(a.media_url))
                if os.path.exists(fp):
                    os.remove(fp)
            s.delete(a); n += 1
        s.commit()
        print(f"[full-daily] cleared {n} old daily videos (seed 16 kept)")
    finally:
        s.close()


def main():
    print("[full-daily] === 1) web research + ingest verified trends ===")
    s = SessionLocal()
    try:
        res = research_and_ingest(s, per_niche=int(_rounds()))
        print(f"[full-daily] research ingested: {res}")
    finally:
        s.close()

    if "--keep" not in sys.argv:
        print("[full-daily] === 2) clear yesterday's daily ===")
        _clear_old_daily()

    print("[full-daily] === 3) generate --from-trends ===")
    subprocess.run([PY, "scripts/run_daily_cycle.py", "--from-trends", "--rounds", _rounds()],
                   cwd=_BACKEND, timeout=5400)

    print("[full-daily] === 4) Obsidian daily calendar ===")
    subprocess.run([PY, "scripts/gen_obsidian_daily.py"], cwd=ROOT, timeout=300)
    print("[full-daily] DONE")


if __name__ == "__main__":
    main()
