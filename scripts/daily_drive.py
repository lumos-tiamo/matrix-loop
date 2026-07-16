#!/usr/bin/env python3
"""matrix-loop DAILY DRIVER — the autonomous "self-driving" job (run by launchd once a day).

One deterministic pass that keeps the matrix producing FRESH daily content WITHOUT manual work:
  1. REFRESH DATA  — drop the CoinGecko OHLC cache so charts re-fetch live prices on render
  2. DAILY 16      — run_daily_cycle: 4 accounts x 4 = 16 FRESH hot-topic videos (hf_gen_*),
                     each scheduled (posting_time) via the A brain + hyperframes provider.
                     ADDITIVE — never overwrites the curated seed 16 (hf_<pid>.mp4).
  3. OBSIDIAN      — refresh the seed publish set (the daily 16 live in the frontend /schedule
                     calendar; the DB is the source of truth for daily content).
Each stage is isolated; a failure logs and the pass continues. Publish stays human-gated.

Flags:
  --rebuild-seed   re-render the curated seed 16 (produce2 all) — EXPLICIT only, overwrites them.
  --no-daily       skip the daily-16 generation (data + obsidian only).
Logs: ~/matrix-loop/logs/daily_drive_YYYY-MM-DD.log (also stdout).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime

ROOT = "/Users/aa00102/matrix-loop"
BATCH = os.path.join(ROOT, "hyperframes-batch")
BACKEND = os.path.join(ROOT, "backend")
PY = os.path.join(BACKEND, ".venv", "bin", "python")
CAP = os.path.join(BATCH, "captures")
LOGDIR = os.path.join(ROOT, "logs")
OHLC_MAX_AGE_H = 12


def log(msg: str):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(LOGDIR, exist_ok=True)
        with open(os.path.join(LOGDIR, f"daily_drive_{datetime.now():%Y-%m-%d}.log"), "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def stage(name, fn):
    log(f"── {name} ──")
    t0 = time.time()
    try:
        fn()
        log(f"   ✓ {name} ({time.time()-t0:.0f}s)")
        return True
    except Exception as e:  # noqa: BLE001 — a bad stage must not abort the whole daily pass
        log(f"   ✗ {name} FAILED: {e.__class__.__name__}: {e}")
        return False


def refresh_data():
    """Age out the OHLC cache so the next render re-fetches live candles (daily 'fresh data')."""
    if not os.path.isdir(CAP):
        log("   (no captures dir yet — charts fetch fresh on first render)")
        return
    now = time.time()
    dropped = 0
    for f in os.listdir(CAP):
        if f.startswith("ohlc_") and f.endswith(".json"):
            p = os.path.join(CAP, f)
            if now - os.path.getmtime(p) > OHLC_MAX_AGE_H * 3600:
                os.remove(p)
                dropped += 1
    log(f"   dropped {dropped} stale OHLC cache file(s) -> live re-fetch on render")


def daily_16():
    """Generate the day's 16 fresh scheduled videos (additive). NEVER touches the seed 16."""
    r = subprocess.run([PY, "scripts/run_daily_cycle.py", "--rounds", "4"],
                       cwd=BACKEND, capture_output=True, text=True, timeout=5400)
    for ln in r.stdout.strip().splitlines()[-6:]:
        log(f"   {ln}")
    if "DAILY_BATCH" not in r.stdout:
        raise RuntimeError("run_daily_cycle did not report DAILY_BATCH")


def rebuild_seed():
    """EXPLICIT only: re-render the curated seed 16 (overwrites hf_<pid>.mp4)."""
    r = subprocess.run([PY, "produce2.py", "all", "--quality=draft"],
                       cwd=BATCH, capture_output=True, text=True, timeout=5400)
    log(f"   {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else '(no output)'}")


def obsidian():
    r = subprocess.run(["python3", "scripts/gen_obsidian_publish.py"],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    log(f"   {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else '(no output)'}")


def main():
    argv = sys.argv[1:]
    log(f"===== DAILY DRIVE {datetime.now().isoformat()} =====")
    stage("1 refresh live data (OHLC)", refresh_data)
    if "--rebuild-seed" in argv:
        stage("* rebuild curated seed 16 (overwrites)", rebuild_seed)
    if "--no-daily" not in argv:
        stage("2 daily 16 (fresh, scheduled, additive)", daily_16)
    stage("3 export seed set to Obsidian", obsidian)
    log("===== DAILY DRIVE COMPLETE =====")


if __name__ == "__main__":
    main()
