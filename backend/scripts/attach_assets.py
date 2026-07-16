#!/usr/bin/env python3
"""Phase C (part 2): for each produced hf_<id>.mp4, attach a VideoAsset (hyperframes, ready,
approved) to the injected script draft + a PublishPlan (from the package's companion content),
so the matrix-loop workbench shows the FULL 6-step pipeline for that card. Idempotent + only
acts on ids whose MP4 exists. Run from backend/:  .venv/bin/python scripts/attach_assets.py
"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.abspath("."))
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Account, LoopRun, Draft, VideoAsset, PublishPlan

BATCH_TAG = "BATCH-2026-07-16"
VIDEOS = os.path.abspath("./data/videos")
PKGS = {p["id"]: p for p in json.load(open("/Users/aa00102/matrix-loop/_content_packages_2026-07-16.json"))["packages"]}
SLOT = {"twitter": "first_reply", "instagram": "link_sticker_bio", "tiktok": "bio"}


def dur(path):
    try:
        o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nk=1:nw=1", path], capture_output=True, text=True)
        return float(o.stdout.strip() or 0)
    except Exception:
        return None


def main():
    db = SessionLocal()
    try:
        run_ids = [r.id for r in db.scalars(select(LoopRun).where(LoopRun.diagnosis == BATCH_TAG)).all()]
        # topic drafts of this batch, keyed by the "[PID]" prefix in their content
        topics = db.scalars(select(Draft).where(Draft.loop_run_id.in_(run_ids), Draft.kind == "topic")).all()
        topic_by_pid = {}
        for t in topics:
            if t.content.startswith("["):
                pid = t.content[1:t.content.index("]")]
                topic_by_pid[pid] = t
        n = 0
        for pid, pkg in PKGS.items():
            mp4 = os.path.join(VIDEOS, f"hf_{pid}.mp4")
            if not os.path.exists(mp4):
                continue
            topic = topic_by_pid.get(pid)
            if not topic:
                print(f"!! no injected topic for {pid}; run inject_batch.py first"); continue
            script = db.scalar(select(Draft).where(Draft.parent_id == topic.id, Draft.kind == "script"))
            if not script:
                print(f"!! no script draft for {pid}"); continue
            acc = db.get(Account, db.get(LoopRun, topic.loop_run_id).account_id)
            # replace any existing asset for this script (idempotent)
            for a in db.scalars(select(VideoAsset).where(VideoAsset.script_draft_id == script.id)).all():
                for pl in db.scalars(select(PublishPlan).where(PublishPlan.video_asset_id == a.id)).all():
                    db.delete(pl)
                db.delete(a)
            db.flush()
            asset = VideoAsset(account_id=acc.id, script_draft_id=script.id, provider="hyperframes",
                               media_url=f"/media/hf_{pid}.mp4", duration=dur(mp4), cost=0.0,
                               dedup_key=f"batch-{pid}", status="ready", review_status="approved",
                               stage="done", progress=100)
            db.add(asset); db.flush()
            el = pkg.get("externalLink") or {}
            plan = PublishPlan(
                account_id=acc.id, video_asset_id=asset.id, platform=acc.platform,
                caption=pkg.get("platformCaption"), hashtags=list(pkg.get("hashtags") or []),
                external_link_slot=SLOT.get(acc.platform, "bio"),
                external_link_text=(el.get("text") or "")[:2000],
                posting_time=(pkg.get("postingTime") or "")[:120], status="ready")
            db.add(plan)
            n += 1
            print(f"✓ {pid}: asset #{asset.id} (approved) + publish plan -> {acc.handle}")
        db.commit()
        print(f"DONE: attached {n} assets+plans.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
