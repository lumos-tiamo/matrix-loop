#!/usr/bin/env python3
"""Export the DAILY generated videos (non-seed) to Obsidian as a publish calendar — DB-driven, so it
covers whatever run_daily_cycle produced (unlike gen_obsidian_publish which is the curated seed 16).

Reads VideoAsset(+PublishPlan+Account) from the DB, copies each mp4 into the vault, writes one
publish note per video (embedded video + caption + posting time + account + source), and a
per-date calendar. Idempotent. Publish首日 = the earliest posting_time (launch day 07-20).
"""
from __future__ import annotations

import os
import shutil
import sys

_BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, _BACKEND)
os.chdir(_BACKEND)   # config DB path is ./data/matrixloop.db (relative to backend/)

from app.db import SessionLocal  # noqa: E402
from app.models import Account, PublishPlan, VideoAsset  # noqa: E402

VAULT = "/Users/aa00102/Documents/WorkSpace/矩阵账号内容/矩阵流量内容"
VIDS = "/Users/aa00102/matrix-loop/backend/data/videos"
CLIP = os.path.join(VAULT, "20_素材", "日更成片")
ACC_FOLDER = {"askaurea": "Aurea_TikTok", "@AirdropEdge": "AirdropEdge_X",
              "@ClearChartsHQ": "ClearCharts_X", "@quiet.yield": "QuietYield_IG"}
SLOT_LABEL = {"first_reply": "首条回复", "link_sticker_bio": "link sticker + bio", "bio": "bio"}


def main():
    os.makedirs(CLIP, exist_ok=True)
    s = SessionLocal()
    try:
        rows = (s.query(VideoAsset, PublishPlan, Account)
                .join(PublishPlan, PublishPlan.video_asset_id == VideoAsset.id)
                .join(Account, Account.id == VideoAsset.account_id)
                .all())
        by_date: dict[str, list] = {}
        made = 0
        for asset, plan, acc in rows:
            if not asset.media_url:
                continue
            if (asset.dedup_key or "").startswith("batch-"):   # skip seed 16
                continue
            base = os.path.basename(asset.media_url)
            src = os.path.join(VIDS, base)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(CLIP, base))
            pt = plan.posting_time or ""
            d = pt.split(" ")[0] if pt else "未排期"
            folder = ACC_FOLDER.get(acc.handle, "其他")
            note = f"""---
asset_id: {asset.id}
account: "{acc.handle}"
platform: "{acc.platform}"
date: {d}
posting_time: "{pt}"
status: {"已采纳" if asset.review_status == "approved" else asset.review_status}
video: "日更成片/{base}"
source: hyperframes-daily
tags: [矩阵, 日更, 可发布]
---

# {acc.handle} · {d} · asset {asset.id}

> 发布时间 **{pt}** · 外链位 **{SLOT_LABEL.get(plan.external_link_slot or '', plan.external_link_slot or '-')}**

## 🎬 成片
![[日更成片/{base}]]
- 本地: `{src}`
- matrix-loop: http://localhost:8000{asset.media_url}

## 📝 文案(可直接复制)
```
{plan.caption or ''}
```

## ✅ 发布前检查
- [ ] 具体数字/日期已按发布日重核(以来源为准)
- [ ] 合规: NFA / 不喊单{" / 台湾刑度分开" if acc.handle == "askaurea" else ""}
- [ ] 外链就位({SLOT_LABEL.get(plan.external_link_slot or '', '-')})
"""
            path = os.path.join(VAULT, "10_账号", folder, "日更", f"{d}_{asset.id}.md")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").write(note)
            by_date.setdefault(d, []).append((acc.handle, asset.id, pt, asset.review_status))
            made += 1

        # calendar
        cal = ["# 📅 日更发布日历(正式发布首日 2026-07-20)\n",
               "> 每条含嵌入成片+文案+发布时间+外链。按日发布。种子16见另一总览。\n"]
        for d in sorted(by_date):
            cal.append(f"\n## {d} · {len(by_date[d])} 条")
            cal.append("| 账号 | 时间 | asset | 状态 |\n|---|---|---|---|")
            for handle, aid, pt, rev in sorted(by_date[d], key=lambda x: x[2]):
                folder = ACC_FOLDER.get(handle, "其他")
                st = "✅采纳" if rev == "approved" else rev
                cal.append(f"| {handle} | {pt[11:] if len(pt) > 10 else pt} | [[{d}_{aid}]] | {st} |")
        os.makedirs(os.path.join(VAULT, "00_总控"), exist_ok=True)
        open(os.path.join(VAULT, "00_总控", "日更发布日历.md"), "w").write("\n".join(cal))
        print(f"Obsidian 日更: {made} 条笔记 + 成片 -> {CLIP} + 00_总控/日更发布日历.md")
    finally:
        s.close()


if __name__ == "__main__":
    main()
