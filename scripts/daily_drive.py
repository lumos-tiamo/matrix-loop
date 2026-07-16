#!/usr/bin/env python3
"""matrix-loop DAILY DRIVER — the autonomous "self-driving" job (run by launchd/cron once a day).

One deterministic pass that keeps the 4-account matrix fresh and publish-ready WITHOUT manual work:
  1. REFRESH DATA   — drop the CoinGecko OHLC cache so charts re-fetch live prices on render
  2. REFRESH TOPICS — best-effort: ping the backend autopilot loop (needs LLM key) to regenerate
                      hot-topic + script drafts; on no-key it keeps the curated verified packages
                      (never invents unverified numbers — the pre-flight blacklist would block them)
  3. RENDER         — produce2.py all  (HyperFrames, deterministic, pre-flight quality-gated)
  4. REGISTER       — attach_assets.py (matrix-loop: VideoAsset approved + PublishPlan)
  5. OBSIDIAN       — gen_obsidian_publish.py  (the Obsidian export is a STEP OF THE LOOP, not manual)
Each stage is isolated; a failure logs and the pass continues. Publish stays human-gated until
AiToEarn is configured. Everything is idempotent + re-runnable.

Usage:  python3 scripts/daily_drive.py [--no-render] [--topics-only]
Logs:   ~/matrix-loop/logs/daily_drive_YYYY-MM-DD.log  (also stdout)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = "/Users/aa00102/matrix-loop"
BATCH = os.path.join(ROOT, "hyperframes-batch")
PY = os.path.join(ROOT, "backend", ".venv", "bin", "python")
CAP = os.path.join(BATCH, "captures")
LOGDIR = os.path.join(ROOT, "logs")
BACKEND = "http://127.0.0.1:8000"
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
        log("   (no captures dir yet — charts will fetch fresh on first render)")
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


def refresh_topics():
    """Best-effort daily hot-topic refresh via the backend autopilot loop (regenerates topic +
    script drafts using the LLM + current Trends). No-key / backend-down => skip, keep curated."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{BACKEND}/batch/run", method="POST",
                                     data=b"{}", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            body = r.read().decode("utf-8", "ignore")[:200]
        log(f"   backend /batch/run -> {body}")
    except Exception as e:  # noqa: BLE001
        log(f"   topic refresh skipped ({e.__class__.__name__}) — keeping curated verified packages")


def render_all():
    r = subprocess.run([PY, "produce2.py", "all", "--quality=draft"],
                       cwd=BATCH, capture_output=True, text=True, timeout=3600)
    tail = "\n".join(r.stdout.strip().splitlines()[-4:])
    log(f"   {tail}")
    if "DONE" not in r.stdout:
        raise RuntimeError("produce2 did not report DONE")


def register():
    r = subprocess.run([PY, "scripts/attach_assets.py"],
                       cwd=os.path.join(ROOT, "backend"), capture_output=True, text=True, timeout=300)
    log(f"   {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else '(no output)'}")


def obsidian():
    r = subprocess.run(["python3", "scripts/gen_obsidian_publish.py"],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    log(f"   {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else '(no output)'}")


def main():
    argv = sys.argv[1:]
    log(f"===== DAILY DRIVE {datetime.now(timezone.utc).isoformat()} =====")
    stage("1/5 refresh live data (OHLC)", refresh_data)
    stage("2/5 refresh hot topics", refresh_topics)
    if "--topics-only" in argv:
        log("topics-only: stopping before render"); return
    if "--no-render" not in argv:
        stage("3/5 render 16 (HyperFrames, quality-gated)", render_all)
    stage("4/5 register in matrix-loop", register)
    stage("5/5 export to Obsidian (loop step)", obsidian)
    log("===== DAILY DRIVE COMPLETE =====")


if __name__ == "__main__":
    main()
