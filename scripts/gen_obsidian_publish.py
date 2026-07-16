#!/usr/bin/env python3
"""Build a COMPLETE, directly-publishable set in Obsidian: copies each final video into the vault,
writes one 'ready-to-publish' note per video (embedded video + platform caption + hashtags +
external-link + posting time + pre-publish checklist), and a publish calendar + batch index.
Run AFTER produce2.py all. Idempotent."""
import json, os, shutil, subprocess

VAULT = "/Users/aa00102/Documents/WorkSpace/矩阵账号内容/矩阵流量内容"
VIDS = "/Users/aa00102/matrix-loop/backend/data/videos"
PKGS = {p["id"]: p for p in json.load(open("/Users/aa00102/matrix-loop/_content_packages_2026-07-16.json"))["packages"]}
ACC = {
    "AE": dict(folder="10_账号/AirdropEdge_X", handle="Airdrop Edge @AirdropEdge", funnel="Nina", color="#8B5CFF", region="东南亚泛英语", platform="X (Twitter)", slot="首条回复"),
    "CC": dict(folder="10_账号/ClearCharts_X", handle="Clear Charts @ClearChartsHQ", funnel="Nina", color="#38BDF8", region="东南亚泛英语", platform="X (Twitter)", slot="首条回复"),
    "QY": dict(folder="10_账号/QuietYield_IG", handle="Quiet Yield @quiet.yield", funnel="Xaue", color="#F5B301", region="东南亚泛英语", platform="Instagram", slot="link sticker + bio"),
    "AU": dict(folder="10_账号/Aurea_TikTok", handle="Aurea @askaurea", funnel="Nina / Xaue", color="#C6FF3A", region="台湾 🇹🇼", platform="TikTok", slot="bio(未满1000粉)"),
}
ORDER = {"AE": ["AE-4", "AE-2", "AE-1", "AE-3"], "CC": ["CC-1", "CC-4", "CC-2", "CC-3"],
         "QY": ["QY-2", "QY-4", "QY-1", "QY-3"], "AU": ["AU-1", "AU-2", "AU-3", "AU-4"]}
DATES = ["2026-07-17", "2026-07-18", "2026-07-19", "2026-07-20"]
CLIP = os.path.join(VAULT, "20_素材", "成片")
os.makedirs(CLIP, exist_ok=True)

sched = {pid: DATES[i] for _, ids in ORDER.items() for i, pid in enumerate(ids)}


def title(p):
    return (p["scenes"][0].get("onScreenCaption") if p.get("scenes") else "") or p["id"]


def dur(f):
    try:
        o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", f], capture_output=True, text=True)
        return f"{float(o.stdout.strip() or 0):.0f}s"
    except Exception:
        return "?"


made = 0
for pid, p in PKGS.items():
    pre = pid.split("-")[0]; a = ACC[pre]
    mp4 = os.path.join(VIDS, f"hf_{pid}.mp4")
    have = os.path.exists(mp4)
    if have:
        shutil.copy(mp4, os.path.join(CLIP, f"hf_{pid}.mp4"))
    el = p.get("externalLink") or {}
    tags = " ".join(p.get("hashtags") or [])
    date = sched.get(pid, "")
    vid_block = (f"![[成片/hf_{pid}.mp4]]\n\n- 本地: `{VIDS}/hf_{pid}.mp4` ({dur(mp4)})\n- matrix-loop: http://localhost:8000/media/hf_{pid}.mp4"
                 if have else "> ⏳ 成片尚未生成(跑 produce2.py 后重跑本脚本)")
    note = f"""---
id: {pid}
account: "{a['handle']}"
platform: "{a['platform']}"
region: "{a['region']}"
date: {date}
publish_time: "{(p.get('postingTime') or '')[:100].replace(chr(34), ' ')}"
status: ready-to-publish
funnel: "{a['funnel']}"
brand_color: "{a['color']}"
video: "成片/hf_{pid}.mp4"
tags: [矩阵, {pre}, 可发布]
---

# {pid} · {title(p)}

> **{a['handle']}** · {a['platform']} · {a['region']} · 导流 **{a['funnel']}** · 发布 **{date}** {p.get('postingTime','')}

## 🎬 成片(可直接发布)
{vid_block}

## 📝 发布文案(直接复制)
```
{p.get('platformCaption','')}
```
**话题标签**：{tags}

**外链（{a['slot']}）**：{el.get('text','')}

## ✅ 发布前检查
- [ ] 时效/实时价已按发布日重核(带 ⏰ 的选题尤其)
- [ ] 合规:NFA / 不喊单 / 收益不承诺{' / 台湾刑度分开' if pre=='AU' else ''}
- [ ] 外链就位（{a['slot']}）
- [ ] 发布后 {'15分钟内回评' if a['platform'].startswith('X') else '90分钟内回评' if pre=='AU' else '前3天回评'}

## 🎯 3秒钩子
{p.get('hook3s','')}
"""
    path = os.path.join(VAULT, a["folder"], "内容", f"{date}_{pid}_PUBLISH.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(note)
    made += 1

# batch index / calendar
idx = ["# 🚀 可直接发布内容 · 2026-07-16 批次(16 条)\n",
       "> 每条笔记含**嵌入成片 + 平台文案 + 标签 + 外链 + 发布检查**。按日发布。\n"]
for date in DATES:
    idx.append(f"\n## {date}\n| 账号 | 平台 | 选题 | 成片 | 笔记 |\n|---|---|---|---|---|")
    for pre, a in ACC.items():
        pid = next((x for x in ORDER[pre] if sched[x] == date), None)
        if not pid:
            continue
        ok = "✅" if os.path.exists(os.path.join(CLIP, f"hf_{pid}.mp4")) else "⏳"
        idx.append(f"| {a['handle'].split('@')[0].strip()} | {a['platform'].split()[0]} | {pid} {title(PKGS[pid])[:26]} | {ok} | [[{date}_{pid}_PUBLISH]] |")
open(os.path.join(VAULT, "00_总控", "可发布内容总览.md"), "w").write("\n".join(idx))
print(f"Obsidian publish set: {made} notes + videos copied to {CLIP} + 可发布内容总览.md")
