#!/usr/bin/env python3
"""图文 CAROUSEL generator — real-data infographic slides (PNG), a first-class format ALONGSIDE video.

Renders brand-styled HTML slides to PNG via headless Chrome. Images are REAL & credible: real-data
candlesticks (CoinGecko OHLC via _ohlc), real numbers (from the verified package), brand typography —
NO AI-generated images. Output = an N-slide carousel (IG 4:5) = the "6 图讲清" save-bait format.

Usage:  gen_carousel.py <pid> [--out DIR] [--coin ethereum|bitcoin]
        (run from hyperframes-batch/ with the backend venv python)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen_watchable import (  # noqa: E402
    BRAND, CJK_SANS, DN, SANS, SERIF, UP, _ohlc, clean_text, drop_placeholders, hero_number,
)

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PKGS = {p["id"]: p for p in json.load(open("/Users/aa00102/matrix-loop/_content_packages_2026-07-16.json"))["packages"]}
OUT_ROOT = "/Users/aa00102/matrix-loop/backend/data/carousels"
W, H = 1080, 1350


def _fmt(p):
    if p >= 1e6:
        return f"${p/1e6:.2f}M"
    if p >= 1000:
        return f"${p/1000:.1f}K"
    return f"${p:,.2f}"


def _static_candles(coin, accent):
    """Static (full-opacity) real-data candlestick + resistance/invalidation annotation."""
    oh = _ohlc_by_coin(coin)
    if not oh:
        return ""
    seg = oh[-46:]
    lo = min(c[3] for c in seg); hi = max(c[2] for c in seg); span = (hi - lo) or 1
    VW, VH, pad = 1000, 520, 30
    cw = (VW - 2 * pad) / len(seg)

    def yy(p):
        return round(pad + (hi - p) / span * (VH - 2 * pad), 1)
    parts = []
    for k, c in enumerate(seg):
        o, h, l, cl = c[1], c[2], c[3], c[4]
        x = round(pad + k * cw + cw * 0.5, 1)
        col = UP if cl >= o else DN
        bt, bb = yy(max(o, cl)), yy(min(o, cl))
        bw = max(3.0, cw * 0.6)
        parts.append(f'<line x1="{x}" y1="{yy(h)}" x2="{x}" y2="{yy(l)}" stroke="{col}" stroke-width="2"/>')
        parts.append(f'<rect x="{round(x-bw/2,1)}" y="{bt}" width="{round(bw,1)}" height="{round(max(3,bb-bt),1)}" rx="1.5" fill="{col}"/>')
    tail = seg[-12:]
    r_hi = max(c[2] for c in tail); r_lo = min(c[3] for c in tail)
    ann = (f'<line x1="0" y1="{yy(r_hi)}" x2="{VW}" y2="{yy(r_hi)}" stroke="#F5B301" stroke-width="2" opacity="0.9"/>'
           f'<text x="{VW-12}" y="{max(24,yy(r_hi)-8)}" fill="#F5B301" font-size="24" font-weight="700" font-family=\'{SANS}\' text-anchor="end">阻力 {_fmt(r_hi)}</text>'
           f'<line x1="0" y1="{yy(r_lo)}" x2="{VW}" y2="{yy(r_lo)}" stroke="{DN}" stroke-width="2" stroke-dasharray="10 7" opacity="0.9"/>'
           f'<text x="{VW-12}" y="{min(VH-10,yy(r_lo)+28)}" fill="{DN}" font-size="24" font-weight="700" font-family=\'{SANS}\' text-anchor="end">失效位 {_fmt(r_lo)}</text>')
    return (f'<svg viewBox="0 0 {VW} {VH}" style="width:100%;height:520px">' + "".join(parts) + ann + "</svg>")


def _ohlc_by_coin(coin):
    """Load OHLC for an explicit coin (carousel isn't pid-bound); self-heal from CoinGecko on miss."""
    import gen_watchable as G
    cap = G.CAPDIR if hasattr(G, "CAPDIR") else os.path.join(HERE, "captures")
    p = os.path.join(cap, f"ohlc_{coin}.json")
    if os.path.exists(p):
        try:
            return json.load(open(p))
        except Exception:
            pass
    return G._fetch_ohlc(coin, p) or []


def _hero_num(hn):
    pre, val, suf, dec = hn
    return f"{pre}{val:.1f}{suf}" if dec else f"{pre}{int(val):,}{suf}"


def build_slides(pkg, coin=None):
    pre = pkg["id"].split("-")[0]
    b = BRAND.get(pre, BRAND["AE"])
    is_cjk = (pkg.get("language", "") or "").startswith(("繁", "zh"))
    hf = CJK_SANS if is_cjk else SERIF
    acc, acc2 = b["accent"], b["accent2"]
    scenes = [s for s in (pkg.get("scenes") or []) if drop_placeholders(s.get("onScreenCaption", "") or s.get("narration", ""))]
    scenes = scenes[:5]
    coin = coin or {"CC": "bitcoin"}.get(pre)

    css = f"""*{{margin:0;box-sizing:border-box}} html,body{{width:{W}px;height:{H}px}}
body{{position:relative;background:radial-gradient(120% 92% at 50% -12%,{b['bg1']},{b['bg2']});color:#fff;font-family:{SANS};padding:58px 54px;display:flex;flex-direction:column;overflow:hidden}}
.glow{{position:absolute;width:1000px;height:1000px;border-radius:50%;filter:blur(130px);opacity:.34;background:radial-gradient(circle,{acc},transparent 66%);top:-300px;right:-260px;z-index:0}}
.glow2{{position:absolute;width:820px;height:820px;border-radius:50%;filter:blur(130px);opacity:.22;background:radial-gradient(circle,{acc2},transparent 66%);bottom:-280px;left:-240px;z-index:0}}
.grid{{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.05) 1px,transparent 1px);background-size:76px 76px;z-index:0;-webkit-mask-image:linear-gradient(180deg,transparent,#000 38%,#000 72%,transparent)}}
.z{{position:relative;z-index:1;display:flex;flex-direction:column;height:100%}}
.top{{display:flex;align-items:center;gap:12px;font-family:'SF Mono',monospace;font-size:22px}}
.ava{{width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg,{acc},{acc2});display:flex;align-items:center;justify-content:center;font-family:{SERIF};font-weight:800;font-size:28px;color:#05070d;box-shadow:0 0 20px {acc}77}}
.chip{{background:{acc};color:#05070d;font-weight:800;border-radius:9px;padding:6px 15px;letter-spacing:1px}}
.hand{{color:#aeb6c8}} .cnt{{margin-left:auto;color:{acc};font-weight:700}}
.ey{{font-family:'SF Mono',monospace;font-size:24px;letter-spacing:5px;color:{acc};margin:30px 0 10px}}
.hl{{font-family:{hf};font-weight:800;font-size:{'56px' if is_cjk else '60px'};line-height:1.1;letter-spacing:-1px}}
.panel{{position:relative;flex:1;margin:26px 0;border:2px solid {acc}66;border-radius:30px;background:linear-gradient(158deg,{acc}30,{acc}0c 58%,transparent);padding:50px;display:flex;flex-direction:column;justify-content:center;overflow:hidden;box-shadow:inset 0 1px 0 {acc}30,0 22px 60px rgba(0,0,0,.42)}}
.metric{{font-family:'SF Mono',monospace;font-size:23px;letter-spacing:3px;color:{acc};margin-bottom:12px}}
.stat{{font-family:{SERIF};font-weight:800;font-size:180px;line-height:.82;letter-spacing:-5px;text-shadow:0 0 55px {acc}66}}
.lab{{font-size:33px;color:#eaeff7;margin-top:20px;line-height:1.3;font-weight:600}}
.bar{{height:20px;margin-top:30px;border-radius:12px;background:linear-gradient(90deg,{acc},{acc2});box-shadow:0 0 28px {acc}99;max-width:72%}}
.ghost{{position:absolute;top:-46px;right:6px;font-family:{SERIF};font-weight:800;font-size:320px;line-height:1;color:{acc};opacity:.13}}
.stmt{{position:relative;font-family:{hf};font-weight:800;font-size:{'72px' if is_cjk else '76px'};line-height:1.12;letter-spacing:-1px}}
.abar{{width:130px;height:9px;border-radius:9px;margin-top:32px;background:linear-gradient(90deg,{acc},{acc2});box-shadow:0 0 22px {acc}88}}
.exp{{font-size:31px;line-height:1.45;color:#d7dbe6}}
.ft{{display:flex;align-items:center;gap:14px;font-family:'SF Mono',monospace;font-size:20px;color:#8892a6;margin-top:22px}}
.dots b{{color:{acc}}} .swipe{{margin-left:auto;color:{acc};font-weight:700}}
.big{{font-family:{hf};font-weight:800;line-height:1.05;letter-spacing:-2px}}"""

    def frame(inner):
        return (f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head>'
                f'<body><div class="glow"></div><div class="glow2"></div><div class="grid"></div>'
                f'<div class="z">{inner}</div></body></html>')

    def top(n, total):
        return (f'<div class="top"><span class="ava">{b["name"][0]}</span>'
                f'<span class="chip">{b["name"]}</span><span class="hand">{b["fn"]}</span>'
                f'<span class="cnt">{n:02d}/{total:02d}</span></div>')

    def foot(n, total):
        dots = "".join("<b>●</b>" if i < n else "○" for i in range(total))
        return f'<div class="ft"><span class="dots">{dots}</span><span>✓ 已核实 · NFA</span><span class="swipe">左滑 →</span></div>'

    slides, total = [], len(scenes) + 2
    hook = clean_text(drop_placeholders(scenes[0].get("onScreenCaption", "") if scenes else "")) or pkg.get("id")
    slides.append(frame(
        top(1, total)
        + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">'
        + f'<div class="ey">{b.get("cat","")}</div>'
        + f'<div class="big" style="font-size:{"90px" if is_cjk else "100px"}">{hook}</div>'
        + f'<div style="margin-top:42px;display:inline-flex;align-self:flex-start;background:{acc};color:#05070d;'
          f'font-weight:800;font-size:30px;border-radius:14px;padding:16px 30px">{total} 张讲清 · 存下 →</div></div>'
        + foot(1, total)))
    for idx, s in enumerate(scenes):
        head = clean_text(drop_placeholders(s.get("onScreenCaption", "") or ""))
        cap = clean_text(drop_placeholders(s.get("narration", "") or ""))[:130]
        hn = hero_number(s.get("onScreenCaption", "")) or hero_number(s.get("narration", ""))
        has_unit = bool(hn and (hn[0] or hn[2]))   # only $ ~ prefix or %/x/B/M/K suffix — no bare "3"/"22"
        is_chart = bool(coin and idx == min(1, len(scenes) - 1))
        if is_chart:
            panel = f'<div class="panel">{_static_candles(coin, acc)}</div>'
            hl = f'<div class="hl">{head}</div>'
        elif has_unit:
            lab = re.sub(r"^[^:：]*[:：]\s*", "", head) or head
            panel = (f'<div class="panel"><div class="metric">数据 · 已核实</div>'
                     f'<div class="stat">{_hero_num(hn)}</div><div class="bar"></div><div class="lab">{lab}</div></div>')
            hl = f'<div class="hl">{head}</div>'
        else:   # STATEMENT slide — filled + designed (big serif + ghost index + accent bar)
            panel = (f'<div class="panel"><div class="ghost">{idx+1:02d}</div>'
                     f'<div class="stmt">{head}</div><div class="abar"></div></div>')
            hl = ""
        slides.append(frame(
            top(idx + 2, total) + f'<div class="ey">{idx+1:02d} / {total-2:02d}</div>'
            + hl + panel + f'<div class="exp">{cap}</div>' + foot(idx + 2, total)))
    fn = "Xaue" if pre == "QY" else ("Nina / Xaue" if pre == "AU" else "Nina")
    slides.append(frame(
        top(total, total)
        + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">'
        + f'<div class="ey">存下 · 转给朋友</div>'
        + f'<div class="big" style="font-size:{"78px" if is_cjk else "82px"}">想一句话搞懂?<br>让 <span style="color:{acc}">{fn}</span> 帮你查。</div>'
        + f'<div class="exp" style="margin-top:36px">{b["fn"]} · 主页链接 · 非投资建议 NFA</div></div>'
        + foot(total, total)))
    return slides


def _viz_compare(items, acc, acc2):
    """Horizontal comparison bars (X vs Y ...) from real values. items = [[label, value, display], ...]"""
    vals = [float(v) for _, v, _ in items] or [1]
    mx = max(vals) or 1
    rows = []
    for lab, v, disp in items:
        w = max(7, round(float(v) / mx * 100))
        rows.append(
            f'<div style="margin:26px 0"><div style="display:flex;justify-content:space-between;font-size:31px;margin-bottom:12px">'
            f'<span style="color:#e2e8f4">{lab}</span><span style="font-family:{SERIF};font-weight:800;color:#fff">{disp}</span></div>'
            f'<div style="height:38px;border-radius:12px;background:#ffffff10"><div style="height:100%;width:{w}%;border-radius:12px;'
            f'background:linear-gradient(90deg,{acc},{acc2});box-shadow:0 0 22px {acc}88"></div></div></div>')
    return "".join(rows)


def _viz_donut(pct, label, acc):
    import math
    r = 148
    c = 2 * math.pi * r
    off = c * (1 - max(0, min(100, pct)) / 100)
    return (f'<div style="display:flex;align-items:center;gap:44px;height:100%">'
            f'<svg width="360" height="360" viewBox="0 0 360 360" style="flex:none">'
            f'<circle cx="180" cy="180" r="{r}" fill="none" stroke="#ffffff12" stroke-width="36"/>'
            f'<circle cx="180" cy="180" r="{r}" fill="none" stroke="{acc}" stroke-width="36" stroke-linecap="round" '
            f'stroke-dasharray="{c:.0f}" stroke-dashoffset="{off:.0f}" transform="rotate(-90 180 180)" '
            f'style="filter:drop-shadow(0 0 16px {acc}aa)"/>'
            f'<text x="180" y="205" text-anchor="middle" font-family="{SERIF}" font-weight="800" font-size="112" fill="#fff">{pct}%</text></svg>'
            f'<div style="font-size:40px;color:#eaeff7;font-weight:700;line-height:1.3">{label}</div></div>')


def _viz_rank(items, acc, acc2):
    """Leaderboard: sorted bars with rank numbers. items = [[label, value, display], ...]"""
    items = sorted(items, key=lambda x: -float(x[1]))
    mx = max((float(v) for _, v, _ in items), default=1) or 1
    rows = []
    for i, (lab, v, disp) in enumerate(items):
        w = max(9, round(float(v) / mx * 100))
        rows.append(
            f'<div style="display:flex;align-items:center;gap:20px;margin:18px 0">'
            f'<span style="font-family:{SERIF};font-weight:800;font-size:36px;color:{acc};width:46px">{i+1}</span>'
            f'<div style="flex:1"><div style="display:flex;justify-content:space-between;font-size:28px;margin-bottom:9px">'
            f'<span style="color:#e2e8f4">{lab}</span><span style="font-weight:800;color:#fff">{disp}</span></div>'
            f'<div style="height:26px;border-radius:9px;background:#ffffff10"><div style="height:100%;width:{w}%;border-radius:9px;'
            f'background:linear-gradient(90deg,{acc},{acc2})"></div></div></div></div>')
    return "".join(rows)


def build_spec_slides(spec, pre, is_cjk):
    """Render a carousel from a STRUCTURED infographic spec (professional data-viz, real numbers).
    spec = {cover, slides:[{kind, ...}], cta}. kind ∈ stat|compare|donut|rank|chart|statement."""
    b = BRAND.get(pre, BRAND["AE"])
    hf = CJK_SANS if is_cjk else SERIF
    acc, acc2 = b["accent"], b["accent2"]
    slides_spec = (spec.get("slides") or [])[:5]
    total = len(slides_spec) + 2
    css = f"""*{{margin:0;box-sizing:border-box}} html,body{{width:{W}px;height:{H}px}}
body{{position:relative;background:radial-gradient(120% 92% at 50% -12%,{b['bg1']},{b['bg2']});color:#fff;font-family:{SANS};padding:58px 54px;display:flex;flex-direction:column;overflow:hidden}}
.glow{{position:absolute;width:1000px;height:1000px;border-radius:50%;filter:blur(130px);opacity:.32;background:radial-gradient(circle,{acc},transparent 66%);top:-300px;right:-260px;z-index:0}}
.glow2{{position:absolute;width:820px;height:820px;border-radius:50%;filter:blur(130px);opacity:.20;background:radial-gradient(circle,{acc2},transparent 66%);bottom:-280px;left:-240px;z-index:0}}
.grid{{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.05) 1px,transparent 1px);background-size:76px 76px;z-index:0;-webkit-mask-image:linear-gradient(180deg,transparent,#000 38%,#000 72%,transparent)}}
.z{{position:relative;z-index:1;display:flex;flex-direction:column;height:100%}}
.top{{display:flex;align-items:center;gap:12px;font-family:'SF Mono',monospace;font-size:22px}}
.ava{{width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg,{acc},{acc2});display:flex;align-items:center;justify-content:center;font-family:{SERIF};font-weight:800;font-size:28px;color:#05070d;box-shadow:0 0 20px {acc}77}}
.chip{{background:{acc};color:#05070d;font-weight:800;border-radius:9px;padding:6px 15px;letter-spacing:1px}}
.hand{{color:#aeb6c8}} .cnt{{margin-left:auto;color:{acc};font-weight:700}}
.ey{{font-family:'SF Mono',monospace;font-size:24px;letter-spacing:5px;color:{acc};margin:30px 0 10px}}
.hl{{font-family:{hf};font-weight:800;font-size:{'54px' if is_cjk else '58px'};line-height:1.1;letter-spacing:-1px}}
.panel{{position:relative;flex:1;margin:24px 0;border:2px solid {acc}66;border-radius:30px;background:linear-gradient(158deg,{acc}2b,{acc}0a 58%,transparent);padding:46px;display:flex;flex-direction:column;justify-content:center;overflow:hidden;box-shadow:inset 0 1px 0 {acc}30,0 22px 60px rgba(0,0,0,.42)}}
.metric{{font-family:'SF Mono',monospace;font-size:23px;letter-spacing:3px;color:{acc};margin-bottom:12px}}
.stat{{font-family:{SERIF};font-weight:800;font-size:170px;line-height:.82;letter-spacing:-5px;text-shadow:0 0 55px {acc}66}}
.delta{{display:inline-block;margin-top:20px;font-size:28px;font-weight:700;color:#05070d;background:{acc};border-radius:10px;padding:8px 18px}}
.pt{{font-family:{hf};font-weight:800;font-size:34px;margin-bottom:6px}}
.exp{{font-size:31px;line-height:1.45;color:#d7dbe6}}
.ft{{display:flex;align-items:center;gap:14px;font-family:'SF Mono',monospace;font-size:20px;color:#8892a6;margin-top:22px}}
.dots b{{color:{acc}}} .swipe{{margin-left:auto;color:{acc};font-weight:700}}
.big{{font-family:{hf};font-weight:800;line-height:1.05;letter-spacing:-2px}}
.ghost{{position:absolute;top:-46px;right:6px;font-family:{SERIF};font-weight:800;font-size:300px;line-height:1;color:{acc};opacity:.13}}
.stmt{{position:relative;font-family:{hf};font-weight:800;font-size:{'66px' if is_cjk else '70px'};line-height:1.12}}"""

    def frame(inner):
        return (f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head>'
                f'<body><div class="glow"></div><div class="glow2"></div><div class="grid"></div>'
                f'<div class="z">{inner}</div></body></html>')

    def top(n):
        return (f'<div class="top"><span class="ava">{b["name"][0]}</span><span class="chip">{b["name"]}</span>'
                f'<span class="hand">{b["fn"]}</span><span class="cnt">{n:02d}/{total:02d}</span></div>')

    def foot(n):
        dots = "".join("<b>●</b>" if i < n else "○" for i in range(total))
        return f'<div class="ft"><span class="dots">{dots}</span><span>✓ 已核实 · NFA</span><span class="swipe">左滑 →</span></div>'

    out = []
    hook = spec.get("cover") or b["name"]
    out.append(frame(top(1) + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">'
                     + f'<div class="ey">{b.get("cat","")}</div>'
                     + f'<div class="big" style="font-size:{"88px" if is_cjk else "98px"}">{hook}</div>'
                     + f'<div style="margin-top:42px;display:inline-flex;align-self:flex-start;background:{acc};color:#05070d;font-weight:800;font-size:30px;border-radius:14px;padding:16px 30px">{total} 张讲清 · 存下 →</div></div>'
                     + foot(1)))
    for i, sl in enumerate(slides_spec):
        kind = sl.get("kind", "statement")
        cap = (sl.get("caption") or "")[:130]
        title = sl.get("title") or sl.get("label") or ""
        if kind == "stat":
            inner = (f'<div class="metric">数据 · 已核实</div><div class="stat">{sl.get("big","")}</div>'
                     + (f'<div class="delta">{sl.get("delta","")}</div>' if sl.get("delta") else "")
                     + f'<div class="exp" style="margin-top:22px;color:#eaeff7;font-weight:600">{sl.get("label","")}</div>')
            body = f'<div class="hl">{title}</div>' if title and title != sl.get("label") else ""
        elif kind == "compare":
            inner = (f'<div class="pt">{title}</div>' if title else "") + _viz_compare(sl.get("items", []), acc, acc2)
            body = ""
        elif kind == "donut":
            inner = _viz_donut(int(sl.get("pct", 0)), sl.get("label", ""), acc)
            body = f'<div class="hl">{title}</div>' if title and title != sl.get("label") else ""
        elif kind == "rank":
            inner = (f'<div class="pt">{title}</div>' if title else "") + _viz_rank(sl.get("items", []), acc, acc2)
            body = ""
        elif kind == "chart":
            inner = _static_candles(sl.get("coin", "bitcoin"), acc)
            body = f'<div class="hl">{title}</div>' if title else ""
        else:  # statement
            inner = f'<div class="ghost">{i+1:02d}</div><div class="stmt">{title or sl.get("label","")}</div>'
            body = ""
        out.append(frame(top(i + 2) + f'<div class="ey">{i+1:02d} / {total-2:02d}</div>' + body
                         + f'<div class="panel">{inner}</div><div class="exp">{cap}</div>' + foot(i + 2)))
    fn = "Xaue" if pre == "QY" else ("Nina / Xaue" if pre == "AU" else "Nina")
    out.append(frame(top(total) + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">'
                     + '<div class="ey">存下 · 转给朋友</div>'
                     + f'<div class="big" style="font-size:{"76px" if is_cjk else "80px"}">{spec.get("cta") or "想一句话搞懂?"}<br>让 <span style="color:{acc}">{fn}</span> 帮你查。</div>'
                     + f'<div class="exp" style="margin-top:36px">{b["fn"]} · 主页链接 · 非投资建议 NFA</div></div>' + foot(total)))
    return out


def render_spec(spec, pre, is_cjk, out_dir):
    pngs = _shoot(build_spec_slides(spec, pre, is_cjk), out_dir)
    print(f"✓ carousel[spec] {pre}: {len(pngs)} slides -> {out_dir}")
    return pngs


def _shoot(slides, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    # clear stale slides so a shorter regen doesn't leave orphans
    for f in os.listdir(out_dir):
        if f.startswith("slide") and f.endswith((".png", ".html")):
            os.remove(os.path.join(out_dir, f))
    pngs = []
    for i, html in enumerate(slides):
        hp = os.path.join(out_dir, f"slide{i+1}.html")
        pp = os.path.join(out_dir, f"slide{i+1}.png")
        open(hp, "w").write(html)
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                        "--force-device-scale-factor=2", f"--window-size={W},{H}",  # 2x retina — crisp IG quality
                        "--virtual-time-budget=1800", f"--screenshot={pp}", f"file://{hp}"],
                       capture_output=True, timeout=90)
        if os.path.exists(pp):
            pngs.append(pp)
    return pngs


def render_pkg(pkg, out_dir, coin=None):
    """Render a carousel from an ad-hoc package (id, language, scenes) — used by the daily/trend path."""
    pngs = _shoot(build_slides(pkg, coin), out_dir)
    print(f"✓ carousel {pkg.get('id')}: {len(pngs)} slides -> {out_dir}")
    return pngs


def render_carousel(pid, out_dir=None, coin=None):
    pkg = PKGS.get(pid)
    if not pkg:
        print(f"!! no package {pid}"); return None
    return render_pkg(pkg, out_dir or os.path.join(OUT_ROOT, pid), coin)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    coin = None
    for a in sys.argv[1:]:
        if a.startswith("--coin"):
            coin = a.split("=")[-1]
    for pid in (args or ["QY-2"]):
        render_carousel(pid, coin=coin)
