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


def _stat_block(hn, accent):
    pre, val, suf, dec = hn
    num = f"{pre}{val:.1f}{suf}" if dec else f"{pre}{int(val):,}{suf}"
    return (f'<div style="font-family:{SERIF};font-size:220px;font-weight:800;line-height:.9;letter-spacing:-3px">{num}</div>'
            f'<div style="height:14px;margin-top:26px;border-radius:8px;background:linear-gradient(90deg,{accent},{accent}22)"></div>')


def build_slides(pkg, coin=None):
    pre = pkg["id"].split("-")[0]
    b = BRAND.get(pre, BRAND["AE"])
    is_cjk = (pkg.get("language", "") or "").startswith(("繁", "zh"))
    hf = CJK_SANS if is_cjk else SERIF
    scenes = [s for s in (pkg.get("scenes") or []) if drop_placeholders(s.get("onScreenCaption", "") or s.get("narration", ""))]
    scenes = scenes[:5]
    coin = coin or {"CC": "bitcoin"}.get(pre)

    def frame(inner, n, total):
        return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;box-sizing:border-box}} html,body{{width:{W}px;height:{H}px}}
body{{background:radial-gradient(120% 90% at 20% 0%,{b['bg1']},{b['bg2']});color:#fff;
font-family:{SANS};padding:64px 60px;display:flex;flex-direction:column;overflow:hidden}}
.hd{{display:flex;align-items:center;justify-content:space-between;font-family:'SF Mono',monospace;font-size:22px;letter-spacing:2px}}
.pill{{border:1.5px solid {b['accent']};color:{b['accent']};border-radius:999px;padding:5px 16px}}
.ey{{font-family:'SF Mono',monospace;font-size:22px;letter-spacing:6px;color:{b['accent']};margin-bottom:14px}}
.hl{{font-family:{hf};font-weight:800;font-size:{ '60px' if is_cjk else '66px'};line-height:1.12;letter-spacing:-1px}}
.cap{{font-size:34px;line-height:1.45;color:#d7dbe6;margin-top:auto}}
.ft{{display:flex;justify-content:space-between;font-family:'SF Mono',monospace;font-size:20px;color:#8892a6;margin-top:30px}}
.viz{{margin:38px 0}}
</style></head><body>
<div class="hd"><span class="pill">{b['name']}</span><span>{b['fn']}</span></div>
{inner}
<div class="ft"><span>{'●'*n}{'○'*(total-n)}</span><span>NFA · 数据可核</span></div>
</body></html>"""

    slides = []
    total = len(scenes) + 2
    hook = clean_text(drop_placeholders(scenes[0].get("onScreenCaption", "") if scenes else "")) or pkg.get("id")
    # cover
    slides.append(frame(
        f'<div style="margin:auto 0"><div class="ey">{b["name"]}</div>'
        f'<div class="hl" style="font-size:{ "72px" if is_cjk else "80px"}">{hook}</div>'
        f'<div style="margin-top:34px"><span class="pill" style="font-size:26px">{total} 图讲清 · 存下</span></div></div>',
        1, total))
    # content
    for idx, s in enumerate(scenes):
        head = clean_text(drop_placeholders(s.get("onScreenCaption", "") or ""))
        cap = clean_text(drop_placeholders(s.get("narration", "") or ""))[:110]
        hn = hero_number(s.get("onScreenCaption", "")) or hero_number(s.get("narration", ""))
        if coin and idx == min(1, len(scenes) - 1):
            viz = f'<div class="viz">{_static_candles(coin, b["accent"])}</div>'
        elif hn:
            viz = f'<div class="viz">{_stat_block(hn, b["accent"])}</div>'
        else:
            viz = '<div class="viz" style="height:8px;width:120px;background:%s;border-radius:6px"></div>' % b["accent"]
        slides.append(frame(f'<div class="ey">{idx+1:02d}</div><div class="hl">{head}</div>{viz}'
                            f'<div class="cap">{cap}</div>', idx + 2, total))
    # cta
    fn = "Xaue" if pre == "QY" else ("Nina / Xaue" if pre == "AU" else "Nina")
    slides.append(frame(
        f'<div style="margin:auto 0"><div class="ey">存下 · 转给朋友</div>'
        f'<div class="hl">想一句话搞懂?<br>让 {fn} 帮你查。</div>'
        f'<div class="cap" style="margin-top:40px">{b["fn"]} · 主页链接 · 非投资建议 NFA</div></div>',
        total, total))
    return slides


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
                        "--force-device-scale-factor=1", f"--window-size={W},{H}",
                        "--virtual-time-budget=1500", f"--screenshot={pp}", f"file://{hp}"],
                       capture_output=True, timeout=60)
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
