#!/usr/bin/env python3
"""Generate the Obsidian daily-publishing vault for the 2026-07-16 matrix content batch.
Reads the 16 verified content packages and writes a structured vault (00_总控/10_账号/20_素材/90_复盘
+ 发布日历) into the existing Obsidian vault WITHOUT clobbering old folders."""
import json, os, re

VAULT = "/Users/aa00102/Documents/WorkSpace/矩阵账号内容/矩阵流量内容"
PKGS = json.load(open("/Users/aa00102/matrix-loop/_content_packages_2026-07-16.json"))["packages"]

# per-account meta: folder, funnel endpoint, brand color, region
ACCT = {
    "AE": dict(folder="10_账号/AirdropEdge_X", handle="Airdrop Edge @AirdropEdge", funnel="Nina",
               color="#8B5CFF", region="东南亚泛英语(新/马/菲)", platform="X (Twitter)"),
    "CC": dict(folder="10_账号/ClearCharts_X", handle="Clear Charts @ClearChartsHQ", funnel="Nina",
               color="#38BDF8", region="东南亚泛英语(新/马/菲)", platform="X (Twitter)"),
    "QY": dict(folder="10_账号/QuietYield_IG", handle="Quiet Yield @quiet.yield", funnel="Xaue",
               color="#F5B301", region="东南亚泛英语(新/马/菲)", platform="Instagram"),
    "AU": dict(folder="10_账号/Aurea_TikTok", handle="Aurea @askaurea", funnel="Nina / Xaue",
               color="#C6FF3A", region="台湾 🇹🇼", platform="TikTok"),
}
# publish schedule: front-load time-sensitive pieces (Day1=07-17 ... Day4=07-20)
ORDER = {
    "AE": ["AE-4", "AE-2", "AE-1", "AE-3"],   # GRVT(07-17) & Hyperlynx 2x first
    "CC": ["CC-1", "CC-4", "CC-2", "CC-3"],   # ETH squeeze & BTC map first
    "QY": ["QY-2", "QY-4", "QY-1", "QY-3"],   # gold volume & whale proof first
    "AU": ["AU-1", "AU-2", "AU-3", "AU-4"],   # 台湾新法 first
}
DATES = ["2026-07-17", "2026-07-18", "2026-07-19", "2026-07-20"]
# time-sensitive flags (recheck-before-publish)
TIMED = {
    "AE-4": "GRVT Multiplier 截 07-17 / TGE 07-21 — 发布前按当日重算,过期即换",
    "AE-2": "Hyperlynx Genesis 2x 有截止(7月初口径) — 发布前重算",
    "CC-1": "ETH 盘面时效 — 发布前核对当日价/OI",
    "CC-4": "BTC 盘面时效 — 发布前核对当日价",
    "QY-4": "链上数据时效 — 发布前核对 PAXG 日活/RWA 市值",
    "AU-4": "情绪/宏观时效 — 发布前核对恐惧贪婪指数",
}

def slug(s):
    s = re.sub(r"[^\w一-鿿]+", "-", s.strip())[:40].strip("-")
    return s or "post"

def ensure(d):
    os.makedirs(os.path.join(VAULT, d), exist_ok=True)

for d in ["00_总控", "20_素材", "90_复盘"] + [a["folder"] for a in ACCT.values()] + \
         [a["folder"] + "/内容" for a in ACCT.values()]:
    ensure(d)

# id -> (date, note filename)
sched = {}
for pre, ids in ORDER.items():
    for i, pid in enumerate(ids):
        sched[pid] = DATES[i]

by_id = {p["id"]: p for p in PKGS}
notepath = {}

def scenes_table(scenes):
    rows = ["| # | 时间 | 口播 / 要点 | 屏幕字幕 | 画面(★=真实素材) |",
            "|---|---|---|---|---|"]
    for s in scenes:
        nar = (s.get("narration") or "").replace("\n", " ").replace("|", "\\|")
        cap = (s.get("onScreenCaption") or "").replace("\n", " ").replace("|", "\\|")
        vis = (s.get("visual") or "").replace("\n", " ").replace("|", "\\|")
        rows.append(f"| {s.get('index','')} | {s.get('seconds','')} | {nar} | {cap} | {vis} |")
    return "\n".join(rows)

for pid, p in by_id.items():
    pre = pid.split("-")[0]
    a = ACCT[pre]
    date = sched[pid]
    title = (p.get("scenes") and p["scenes"][0] and p.get("hook3s")) or pid
    ttl = p.get("hook3s", pid)
    # derive a short title from first scene caption or id
    disp_title = (p["scenes"][0].get("onScreenCaption") if p.get("scenes") else "") or pid
    fname = f"{date}_{pid}_{slug(disp_title)}.md"
    rel = f"{a['folder']}/内容/{fname}"
    notepath[pid] = (rel, fname)
    el = p.get("externalLink") or {}
    facts = "\n".join(f"- {f.get('fact','')} — _{f.get('source','')}_" for f in (p.get("factsUsed") or []))
    tags = p.get("hashtags") or []
    timed = TIMED.get(pid, "")
    qa = p.get("qa") or {}
    fm = f"""---
id: {pid}
account: "{a['handle']}"
platform: "{p.get('platform','')}"
region: "{a['region']}"
language: "{p.get('language','')}"
date: {date}
publish_time: "{p.get('postingTime','').replace(chr(34),' ')[:120]}"
status: draft
format: "{p.get('format','') or ''}"
funnel: "{a['funnel']}"
hotspot_verify: confirmed
external_link_slot: "{el.get('slot','')[:60]}"
brand_color: "{a['color']}"
time_sensitive: {"true" if timed else "false"}
tags: [矩阵, {pre}, "{p.get('platform','').split()[0]}"]
---"""
    body = f"""{fm}

# {pid} · {disp_title}

> **账号** {a['handle']} · **平台** {p.get('platform','')} · **地域** {a['region']} · **导流** {a['funnel']}
> **发布日** {date} · **建议时间** {p.get('postingTime','')}
{"> ⏰ **时效**: " + timed if timed else ""}

**🎯 3秒钩子**：{p.get('hook3s','')}

## 🎬 分镜脚本
{scenes_table(p.get('scenes') or [])}

## 📝 平台文案
```
{p.get('platformCaption','')}
```
**Hashtags**：{' '.join(tags)}

**外链（{el.get('slot','')}）**：
{el.get('text','')}

## 🎨 HyperFrames 出片规范（确定性 · 低AI感）
{p.get('hyperframesSpec','')}

## ✅ 事实与来源（仅已核实）
{facts}

## ⚖️ 合规自检
{p.get('compliance','')}

## 🔎 QA
- pass: **{qa.get('pass')}**
{chr(10).join('- ' + str(i) for i in (qa.get('issues') or [])) or '- （无）'}
"""
    open(os.path.join(VAULT, rel), "w").write(body)

# ---- account profile files ----
for pre, a in ACCT.items():
    prof = f"""# {a['handle']}

- **平台**：{a['platform']}
- **地域**：{a['region']}
- **导流出口**：{a['funnel']}
- **品牌色**：{a['color']}
- **本批 4 条**：{', '.join(f'[[{notepath[i][1][:-3]}]]' for i in ORDER[pre])}

## 涨粉 & 红线（运营总手册）
{"- X:原生视频≈10×、回复权重13.5×赞/转发20×、外链放首条回复、发布15分钟内回评" if a['platform'].startswith('X') else ""}
{"- IG:Reels拉新8×→24h内Carousel沉淀(saves 9×);link sticker+bio 导流;反 degen 反焦虑" if a['platform']=='Instagram' else ""}
{"- TikTok:前3秒禁币价/ticker/'100x'/保证收益、静音70%字幕overlay、晚6-10点(台湾)、前90min回评、70%教育/30%推广;未满1000粉走 bio 导流" if a['platform']=='TikTok' else ""}
- 全账号 NFA(非投资建议)。
"""
    open(os.path.join(VAULT, a["folder"], "_账号档案.md"), "w").write(prof)

# ---- 发布日历 ----
cal = ["# 📅 发布日历 · 2026-07-16 批次(16 条)\n",
       "> 每日一号一条,4 天滚动。status: draft→ready→scheduled→published。⏰=时效,发布前重核。\n"]
for date in DATES:
    cal.append(f"\n## {date}\n")
    cal.append("| 账号 | 平台 | 选题 | 时效 | 笔记 |")
    cal.append("|---|---|---|---|---|")
    for pre, a in ACCT.items():
        pid = next((i for i in ORDER[pre] if sched[i] == date), None)
        if not pid: continue
        p = by_id[pid]
        disp = (p["scenes"][0].get("onScreenCaption") if p.get("scenes") else "") or pid
        timed = "⏰" if pid in TIMED else ""
        cal.append(f"| {a['handle'].split('@')[0].strip()} | {a['platform'].split()[0]} | {pid} {disp[:30]} | {timed} | [[{notepath[pid][1][:-3]}]] |")
open(os.path.join(VAULT, "00_总控", "发布日历.md"), "w").write("\n".join(cal))

# ---- 热点弹药库 (verified facts aggregated + discard blacklist) ----
allfacts = []
for p in PKGS:
    for f in (p.get("factsUsed") or []):
        allfacts.append((p["id"], f.get("fact",""), f.get("source","")))
ammo = ["# 🔫 热点弹药库(2026-07-16 · 已对抗性核实)\n",
        "> 只用 confirmed/高置信事实。带截止日的空投/实时价发布前按当日重算。\n",
        "## ✅ 已核实事实(按条目)\n",
        "| 条目 | 事实 | 来源 |", "|---|---|---|"]
PIPE = "\\|"
for pid, fact, src in allfacts:
    ff = fact.replace("|", PIPE)[:140]
    ss = src.replace("|", PIPE)[:60]
    ammo.append(f"| {pid} | {ff} | {ss} |")
ammo += ["\n## ⛔ 黑名单(绝不上字幕 · 编造/过时)\n",
    "- 黄金代币总市值 $71亿/涨300% → 实为约 $5.5B / ~289%",
    "- 「美联储撤降息/新主席/仅1人预期降息」→ 2026 实为加息倾向(维持 3.50-3.75%、9/18 委员预期年内至少加息一次)",
    "- 金价「May 2026 record $4,768」→ 假高点;真实 ATH 约 $5,590 @ 2026-01-28",
    "- Robinhood「7万+ AI agent 账户」→ 无来源",
    "- Ostium「官方称最后一季」→ 无来源,勿造紧迫感",
    "- BUIDL「持仓 250 亿」→ 内部矛盾/疑笔误",
    "- sUSDe「10-15%」旧值 → 用 2026-07 实时约 3.5-8%",
    "- App Store id6771070397 当「可下载 Nina」→ 未核,勿上字幕",
    "\n## ⚖️ 合规",
    "- 台湾刑度分开:无照经营=7年/1亿 vs 诈欺操纵=10年/2亿",
    "- XAUE 收益用「示例约 2%/以黄金计价的低个位数/机构级即将开放」,不承诺固定收益,零售强调白名单",
    "- 挂链门槛:@askaurea(TikTok)+@quiet.yield(IG)未满 1000 粉 → 只能 bio/link sticker;X 外链放首条回复",
]
open(os.path.join(VAULT, "00_总控", "热点弹药库.md"), "w").write("\n".join(ammo))

# ---- 品牌规范 ----
brand = """# 🎨 品牌 & 出片规范

- **分辨率/帧率**：9:16 · 1080×1920 · 30fps · H.264 · 硬字幕(静音 70% 可读)
- **品牌配色**：空投紫 `#8B5CFF`(AirdropEdge) · 交易蓝 `#38BDF8`(ClearCharts) · 收益金 `#F5B301`(QuietYield) · 科普绿 `#C6FF3A`(Aurea)
- **出片引擎**：HyperFrames(HTML→确定性 MP4,零抽卡)；真实素材优先(TradingView 截图 / 链上数据截图 / Nina 对话录屏 / 假交易所对比)降 AI 感
- **Aurea 数字人**：锁定形象 2A(`~/Desktop/私域矩阵_视频生产/04_Aurea_TikTok/_AUREA_锁定形象_2A.png`),10 天同一形象
- 只渲染已核实数字;招牌/画面禁乱码文字
"""
open(os.path.join(VAULT, "20_素材", "品牌规范.md"), "w").write(brand)

# ---- 复盘模板 ----
retro = """# 周复盘模板

| 账号 | 条目 | views | CTR | 评论 | 导流(Nina/Xaue) | 备注 |
|---|---|---|---|---|---|---|

## 假设验证:录屏/真实素材(低AI感) vs 信息图 — 哪个 CTR/留存更高?
## 时效题 vs 常青题表现对比
## 下批改进
"""
open(os.path.join(VAULT, "90_复盘", "_周复盘模板.md"), "w").write(retro)

print("Obsidian vault generated under:", VAULT)
print("notes:", sum(1 for _ in notepath), "| calendar + 弹药库 + 品牌规范 + 账号档案×4 + 复盘模板")
