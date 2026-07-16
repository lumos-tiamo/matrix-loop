#!/usr/bin/env python3
"""CLEAN SLATE — remove every discarded pre-hyperframes video + orphan DB row so the matrix holds
ONLY the 16 hyperframes finals. Destructive + idempotent. Run from backend/ with the venv python.

Keeps EXACTLY the 16 finals: hf_{AE,CC,QY,AU}-{1..4}.mp4 (VideoAssets pointing at them).
Deletes: old faceless_*/waoowaoo_* renders, remotion test renders, orphan tts_/img_ files, and
every VideoAsset (+ its PublishPlan/PublishDispatch) whose media_url is not one of the 16 finals.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal  # noqa: E402
from app.models import PublishPlan, VideoAsset  # noqa: E402

VIDS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "videos")
REMOTION_OUT = "/Users/aa00102/matrix-loop/remotion/out"
IDS = [f"{p}-{n}" for p in ("AE", "CC", "QY", "AU") for n in (1, 2, 3, 4)]
FINAL = {f"hf_{i}.mp4" for i in IDS}


def _basename(url: str | None) -> str:
    return os.path.basename(url or "")


def clean_db():
    s = SessionLocal()
    try:
        assets = s.query(VideoAsset).all()
        junk = [a for a in assets if _basename(a.media_url) not in FINAL]
        junk_ids = [a.id for a in junk]
        kept = [a.id for a in assets if a.id not in junk_ids]
        print(f"DB: {len(assets)} assets -> keep {len(kept)} finals, delete {len(junk_ids)} junk: {junk_ids}")
        if junk_ids:
            # dependent rows first
            try:
                from app.models import PublishDispatch
                d = s.query(PublishDispatch).filter(PublishDispatch.video_asset_id.in_(junk_ids)).delete(synchronize_session=False)
                print(f"    deleted {d} PublishDispatch")
            except Exception as e:  # noqa: BLE001
                print(f"    (PublishDispatch skip: {e})")
            p = s.query(PublishPlan).filter(PublishPlan.video_asset_id.in_(junk_ids)).delete(synchronize_session=False)
            print(f"    deleted {p} PublishPlan")
            n = s.query(VideoAsset).filter(VideoAsset.id.in_(junk_ids)).delete(synchronize_session=False)
            print(f"    deleted {n} VideoAsset")
            s.commit()
    finally:
        s.close()


def clean_files():
    removed, freed = 0, 0
    # 1) data/videos: keep only the 16 hf finals; drop every other media + tts + frame
    if os.path.isdir(VIDS):
        for f in os.listdir(VIDS):
            p = os.path.join(VIDS, f)
            if not os.path.isfile(p):
                continue
            keep = f in FINAL
            junk = (f.endswith((".mp4", ".mov", ".webm")) and not keep) or \
                   f.startswith(("faceless_", "waoowaoo_", "tts_edge_", "tts_say_", "img_")) or \
                   f.endswith(".silent.mp4")
            if junk and not keep:
                freed += os.path.getsize(p)
                os.remove(p)
                removed += 1
    # 2) remotion/out test renders (safe: dev-only, not in DB)
    if os.path.isdir(REMOTION_OUT):
        for root, _dirs, files in os.walk(REMOTION_OUT):
            for f in files:
                if f.endswith((".mp4", ".png")):
                    p = os.path.join(root, f)
                    freed += os.path.getsize(p)
                    os.remove(p)
                    removed += 1
    print(f"FILES: removed {removed} junk files, freed {freed/1e6:.1f} MB")


def verify():
    s = SessionLocal()
    try:
        remaining = s.query(VideoAsset).count()
        finals_on_disk = sum(1 for f in FINAL if os.path.exists(os.path.join(VIDS, f)))
        print(f"VERIFY: {remaining} VideoAsset rows remain · {finals_on_disk}/16 finals present on disk")
    finally:
        s.close()


if __name__ == "__main__":
    print("=== matrix-loop clean slate (keep only 16 hyperframes finals) ===")
    clean_db()
    clean_files()
    verify()
    print("=== done ===")
