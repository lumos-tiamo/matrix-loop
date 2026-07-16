#!/usr/bin/env python3
"""DAILY BATCH — 自动驾驶核心:每天生成 16 条结合热点的最新视频 + 排期。

For each of the 4 accounts, generate ROUNDS(=4) FRESH videos in one run:
  topic (A brain / LLM) -> script (LLM) -> hyperframes video (hf_gen_<brand>_<hash>.mp4)
Each new video gets a PublishPlan with a staggered posting_time (排期), tagged with today's date.
=> 4 accounts x 4 = 16 dated, scheduled, publish-ready ADDITIONAL videos per run. 日更.

NEVER touches the curated seed 16 (hf_<pid>.mp4 — different names + dedup keys). Bounded by the
governor quota. Publish stays human-gated without AiToEarn (content is marked ready/approved).

Usage:  run_daily_cycle.py [--rounds N] [--only <account_id>]   (from backend/, venv python)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.analysis.factory import resolve_llm_client  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Account, Draft, PublishPlan, VideoAsset  # noqa: E402
from app.orchestrator.engine import advance_account  # noqa: E402
from app.video.factory import make_account_provider_resolver  # noqa: E402

ROUNDS = 4  # videos per account per day (4 accounts x 4 = 16/day)
# staggered daily posting hours (local) per account, spread across the day so the matrix drips
SLOTS = {
    9:  [9, 13, 18, 21],    # @AirdropEdge  (X, SEA)
    10: [10, 14, 19, 22],   # @ClearChartsHQ (X, SEA)
    11: [8, 12, 17, 20],    # @quiet.yield  (IG, SEA)
    8:  [12, 15, 19, 22],   # askaurea      (TikTok, TW)
}
LINK_SLOT = {"twitter": "first_reply", "instagram": "link_sticker_bio", "tiktok": "bio"}


def _opt(flag, default=None):
    for i, a in enumerate(sys.argv[1:]):
        if a == flag:
            return sys.argv[1:][i + 1] if i + 1 < len(sys.argv[1:]) else default
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return default


def _newest_asset_id(s, acct_id):
    v = (s.query(VideoAsset).filter(VideoAsset.account_id == acct_id)
         .order_by(VideoAsset.id.desc()).first())
    return v.id if v else 0


def _caption_for(s, asset):
    d = s.get(Draft, asset.script_draft_id) if asset.script_draft_id else None
    txt = (d.content if d else "") or ""
    first = txt.strip().split(". ")[0][:160]
    return first


def main() -> int:
    rounds = int(_opt("--rounds", ROUNDS))
    only = _opt("--only")
    s = SessionLocal()
    try:
        llm = resolve_llm_client()
        resolver = make_account_provider_resolver()   # avatar_handles empty -> hyperframes per brand
        today = datetime.now()   # LOCAL time — posting slots are the user's local calendar
        accounts = s.query(Account).order_by(Account.id).all()
        if only:
            accounts = [a for a in accounts if str(a.id) == str(only)]
        report = {}
        for a in accounts:
            slots = SLOTS.get(a.id, [9, 13, 18, 21])
            report[a.handle] = []
            for r in range(rounds):
                before = _newest_asset_id(s, a.id)
                try:
                    advance_account(s, a, llm=llm, video=resolver, sync=(r == 0))
                except Exception as e:  # noqa: BLE001
                    print(f"  {a.handle} r{r} error: {e.__class__.__name__}: {e}")
                    continue
                after = _newest_asset_id(s, a.id)
                if after <= before:
                    print(f"  {a.handle} r{r}: no new video (quota/dup/blocked)")
                    continue
                asset = s.get(VideoAsset, after)
                hr = slots[r % len(slots)]
                pt = today.replace(hour=hr, minute=0, second=0, microsecond=0)
                if hr < today.hour:      # slot already passed today -> schedule tomorrow
                    pt = pt + timedelta(days=1)
                plan = s.query(PublishPlan).filter(PublishPlan.video_asset_id == after).first()
                if not plan:
                    plan = PublishPlan(account_id=a.id, video_asset_id=after)
                    s.add(plan)
                plan.platform = a.platform
                plan.caption = _caption_for(s, asset)
                plan.external_link_slot = LINK_SLOT.get(a.platform or "", "bio")
                plan.posting_time = pt.strftime("%Y-%m-%d %H:%M")
                plan.status = "ready"
                asset.review_status = "approved"
                s.commit()
                report[a.handle].append({"asset": after, "post_at": plan.posting_time,
                                         "media": asset.media_url})
                print(f"  ✓ {a.handle} r{r}: asset {after} @ {plan.posting_time} -> {asset.media_url}")
        total = sum(len(v) for v in report.values())
        print(f"DAILY_BATCH: {total} videos scheduled")
        print(json.dumps(report, default=str)[:1500])
        return 0
    finally:
        s.close()


if __name__ == "__main__":
    sys.exit(main())
