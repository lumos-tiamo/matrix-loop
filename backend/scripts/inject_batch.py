#!/usr/bin/env python3
"""Phase C (part 1): inject the 16 curated content packages into matrix-loop as
LoopRun + adopted topic Draft + adopted script Draft, so the video workbench UI shows
each piece's pipeline (采纳选题 → 生成脚本 → 采纳脚本 → 待出片). Idempotent: re-running
removes the previous batch (tagged in LoopRun.diagnosis) first.

Run from backend/:  .venv/bin/python scripts/inject_batch.py
"""
import json, sys, os
sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import select
from app.db import SessionLocal
from app.models import Account, LoopRun, Draft, VideoAsset, PublishPlan

BATCH_TAG = "BATCH-2026-07-16"
PKGS = json.load(open("/Users/aa00102/matrix-loop/_content_packages_2026-07-16.json"))["packages"]

HANDLE = {"AE": "@AirdropEdge", "CC": "@ClearChartsHQ", "QY": "@quiet.yield", "AU": "askaurea"}


def topic_content(p):
    disp = (p["scenes"][0].get("onScreenCaption") if p.get("scenes") else "") or p["id"]
    return f"[{p['id']}] {disp}\n\n{p.get('hook3s','')}"


def script_content(p):
    lines = [f"🎯 HOOK (0-3s): {p.get('hook3s','')}", "", "── 分镜口播 ──"]
    for s in p.get("scenes") or []:
        lines.append(f"[{s.get('index','')}·{s.get('seconds','')}] {s.get('narration','')}")
        cap = s.get("onScreenCaption")
        if cap:
            lines.append(f"    字幕: {cap}")
    lines += ["", "── 平台文案 ──", p.get("platformCaption", "")]
    tags = p.get("hashtags") or []
    if tags:
        lines.append("Hashtags: " + " ".join(tags))
    el = p.get("externalLink") or {}
    if el:
        lines += ["", f"外链({el.get('slot','')}): {el.get('text','')}"]
    return "\n".join(lines)


def main():
    db = SessionLocal()
    try:
        # ---- clean previous batch (idempotent) ----
        old_runs = db.scalars(select(LoopRun).where(LoopRun.diagnosis == BATCH_TAG)).all()
        old_run_ids = [r.id for r in old_runs]
        if old_run_ids:
            old_drafts = db.scalars(select(Draft).where(Draft.loop_run_id.in_(old_run_ids))).all()
            old_draft_ids = [d.id for d in old_drafts]
            # remove assets + plans that hang off those scripts
            if old_draft_ids:
                for a in db.scalars(select(VideoAsset).where(VideoAsset.script_draft_id.in_(old_draft_ids))).all():
                    for pl in db.scalars(select(PublishPlan).where(PublishPlan.video_asset_id == a.id)).all():
                        db.delete(pl)
                    db.delete(a)
            for d in old_drafts:
                db.delete(d)
            for r in old_runs:
                db.delete(r)
            db.commit()
            print(f"cleaned previous batch: {len(old_runs)} runs, {len(old_draft_ids)} drafts")

        # ---- group packages by account ----
        by_pre = {}
        for p in PKGS:
            by_pre.setdefault(p["id"].split("-")[0], []).append(p)

        created = 0
        for pre, pkgs in by_pre.items():
            handle = HANDLE[pre]
            acc = db.scalar(select(Account).where(Account.handle == handle))
            if acc is None:
                print(f"!! account not found for handle {handle}; skip")
                continue
            run = LoopRun(account_id=acc.id, diagnosis=BATCH_TAG, status="ok")
            db.add(run)
            db.flush()  # get run.id
            for p in pkgs:
                topic = Draft(loop_run_id=run.id, kind="topic",
                              content=topic_content(p), review_status="adopted")
                db.add(topic)
                db.flush()
                script = Draft(loop_run_id=run.id, kind="script", parent_id=topic.id,
                               content=script_content(p), review_status="adopted")
                db.add(script)
                created += 1
            print(f"{handle}: run #{run.id}, {len(pkgs)} topic+script pairs")
        db.commit()
        print(f"DONE: injected {created} pieces (topic+script, adopted).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
