#!/usr/bin/env python3
"""Phase B: generate one deterministic HyperFrames composition (standalone HTML) per content
package — brand-colored, editorial data-card style (low AI feel, zero gacha). Scenes become
timed clips: big headline (onScreenCaption) + narration subtitle + brand header/footer.
Real-material screenshots (TradingView / on-chain / assets) are overlaid by the human per the
Obsidian note; this renders the branded caption/data layer deterministically.

Usage: python3 gen_hyperframes.py   -> writes compositions/<id>.html for all 16
"""
import json, os, re, html

HERE = os.path.dirname(os.path.abspath(__file__))
PKGS = json.load(open("/Users/aa00102/matrix-loop/_content_packages_2026-07-16.json"))["packages"]
OUT = os.path.join(HERE, "compositions")
os.makedirs(OUT, exist_ok=True)

# brand per prefix: bg, accent, handle, funnel
BRAND = {
    "AE": dict(accent="#8B5CFF", bg1="#120a24", bg2="#05040a", handle="AIRDROP EDGE", funnel="→ Nina"),
    "CC": dict(accent="#38BDF8", bg1="#08192e", bg2="#04070d", handle="CLEAR CHARTS", funnel="→ Nina"),
    "QY": dict(accent="#F5B301", bg1="#241a06", bg2="#0a0803", handle="QUIET YIELD", funnel="→ Xaue"),
    "AU": dict(accent="#C6FF3A", bg1="#16240a", bg2="#070a04", handle="AUREA", funnel="→ Nina / Xaue"),
}


def parse_spans(scenes):
    """Return list of (start, dur) in seconds; contiguous, monotonic."""
    spans = []
    cursor = 0.0
    for s in scenes:
        txt = str(s.get("seconds", "")).lower()
        nums = re.findall(r"\d+(?:\.\d+)?", txt)
        if "slide" in txt or len(nums) < 2:
            start, dur = cursor, 4.0
        else:
            a, b = float(nums[0]), float(nums[1])
            start = max(cursor, a)
            dur = max(1.5, b - a)
        spans.append((round(start, 2), round(dur, 2)))
        cursor = round(start + dur, 2)
    return spans


def headline_size(t):
    n = len(t)
    if n <= 16: return 132
    if n <= 26: return 104
    if n <= 40: return 84
    if n <= 60: return 66
    if n <= 90: return 52
    return 44


def esc(s):
    return html.escape(s or "")


def build(pkg, spans=None):
    pre = pkg["id"].split("-")[0]
    b = BRAND[pre]
    scenes = pkg.get("scenes") or []
    spans = spans or parse_spans(scenes)
    total = round((spans[-1][0] + spans[-1][1]) if spans else 6, 2) + 0.3
    n = len(scenes)
    is_cjk = pkg.get("language", "").startswith("繁")
    is_aurea = (pre == "AU")           # Aurea = 数字人出镜:锁定 2A 形象做常驻主持人
    track = 2 if is_aurea else 1

    clips, tweens = [], []
    for i, (s, (start, dur)) in enumerate(zip(scenes, spans)):
        head = esc(s.get("onScreenCaption") or "")
        narr = esc(s.get("narration") or "")
        hsize = headline_size(s.get("onScreenCaption") or "")
        if is_aurea:
            hsize = min(hsize, 90)
        dots = "".join(
            f'<i class="dot{" on" if j == i else ""}"></i>' for j in range(n)
        )
        clips.append(f"""
      <section id="s{i}" class="clip scene{' aurea' if is_aurea else ''}" data-start="{start}" data-duration="{dur}" data-track-index="{track}">
        <div class="in">
          <div class="top">
            <span class="chip">{esc(b['handle'])}</span>
            <span class="funnel">{esc(b['funnel'])}</span>
          </div>
          <div class="mid">
            <div class="kicker">{i+1:02d} / {n:02d}</div>
            <h1 style="font-size:{hsize}px">{head}</h1>
            <div class="rule"></div>
          </div>
          <div class="bot">
            <p class="narr">{narr}</p>
            <div class="dots">{dots}</div>
            <div class="nfa">NFA · not financial advice</div>
          </div>
        </div>
      </section>""")
        tweens.append(
            f'tl.fromTo("#s{i} .in",{{autoAlpha:0,y:36}},{{autoAlpha:1,y:0,duration:0.5,ease:"power3.out"}},{start});'
        )

    # Aurea 数字人常驻主持人:锁定 2A 形象全幅背景 + 渐变压暗 + 缓慢 Ken Burns(内联 base64,确定性)
    host_clip = host_css = host_tween = ""
    root_bg = (f"background:\n"
               f"          radial-gradient(120% 70% at 78% -8%, {b['accent']}2e, transparent 60%),\n"
               f"          radial-gradient(90% 60% at 0% 108%, {b['accent']}18, transparent 55%),\n"
               f"          linear-gradient(180deg, {b['bg1']}, {b['bg2']});")
    if is_aurea:
        import base64
        _b64 = base64.b64encode(open(os.path.join(HERE, "public", "aurea.png"), "rb").read()).decode()
        root_bg = "background:#05060a;"
        host_clip = (f'\n      <section id="host" class="clip" data-start="0" data-duration="{total}" data-track-index="0">'
                     f'<img id="hostimg" src="data:image/png;base64,{_b64}" alt="Aurea" /><div class="scrim"></div></section>')
        host_tween = f'tl.fromTo("#hostimg",{{scale:1.0}},{{scale:1.07,duration:{total},ease:"none"}},0);'
        host_css = (
            "      .scene.aurea .in { justify-content:flex-end; }\n"
            "      .scene.aurea .top { position:absolute; top:104px; left:84px; right:84px; }\n"
            "      .scene.aurea .mid { flex:0 0 auto; margin-bottom:6px; }\n"
            "      .scene.aurea h1 { text-shadow:0 4px 30px rgba(0,0,0,.9); }\n"
            "      .scene.aurea .kicker { text-shadow:0 2px 12px rgba(0,0,0,.9); }\n"
            "      .scene.aurea .narr { background:#000000aa; }\n"
            "      #hostimg { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; object-position:50% 16%; transform-origin:50% 30%; }\n"
            "      .scrim { position:absolute; inset:0; background:linear-gradient(180deg, rgba(0,0,0,.20) 0%, rgba(0,0,0,0) 24%, rgba(0,0,0,.42) 55%, rgba(0,0,0,.94) 100%); }\n"
        )
    cjk_fonts = '"PingFang TC","Noto Sans TC","Microsoft JhengHei",' if is_cjk else ""
    doc = f"""<!doctype html>
<html lang="{'zh-Hant' if is_cjk else 'en'}" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {{ margin:0; padding:0; box-sizing:border-box; }}
      html, body {{ width:1080px; height:1920px; overflow:hidden; background:#000; }}
      body {{ font-family:{cjk_fonts}"Inter","Helvetica Neue",system-ui,sans-serif; -webkit-font-smoothing:antialiased; }}
      #root {{ position:relative; width:1080px; height:1920px; overflow:hidden;
        {root_bg} }}
      .scene {{ position:absolute; inset:0; }}
      .in {{ position:absolute; inset:0; display:flex; flex-direction:column;
        padding:110px 84px 130px; }}
      .top {{ display:flex; align-items:center; justify-content:space-between; }}
      .chip {{ font-weight:800; letter-spacing:.14em; font-size:30px; color:{b['accent']};
        border:2px solid {b['accent']}66; border-radius:999px; padding:12px 26px; }}
      .funnel {{ font-weight:700; font-size:28px; color:#e9ecf5cc; letter-spacing:.04em; }}
      .mid {{ flex:1; display:flex; flex-direction:column; justify-content:center; }}
      .kicker {{ font-weight:800; font-size:34px; color:{b['accent']}; letter-spacing:.22em; margin-bottom:26px; }}
      h1 {{ color:#fff; font-weight:800; line-height:1.06; letter-spacing:-0.01em;
        text-wrap:balance; max-width:900px; }}
      .rule {{ width:150px; height:8px; border-radius:8px; margin-top:44px;
        background:linear-gradient(90deg,{b['accent']},{b['accent']}22); }}
      .bot {{ display:flex; flex-direction:column; gap:30px; }}
      .narr {{ color:#eef1f7; font-size:40px; line-height:1.42; font-weight:500;
        background:#0000004d; border-left:6px solid {b['accent']}; border-radius:14px;
        padding:26px 30px; max-width:912px; }}
      .dots {{ display:flex; gap:12px; }}
      .dot {{ width:20px; height:20px; border-radius:999px; background:#ffffff22; }}
      .dot.on {{ background:{b['accent']}; box-shadow:0 0 18px {b['accent']}; }}
      .nfa {{ font-size:24px; color:#ffffff66; letter-spacing:.12em; font-weight:600; }}
{host_css}    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-fps="30" data-width="1080" data-height="1920">{host_clip}
{''.join(clips)}
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      {host_tween} {' '.join(tweens)}
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>"""
    return doc, total


if __name__ == "__main__":
    counts = {}
    for p in PKGS:
        doc, total = build(p)
        path = os.path.join(OUT, f"{p['id']}.html")
        open(path, "w").write(doc)
        counts[p["id"]] = total
    print("generated:", len(counts), "compositions")
    for k, v in counts.items():
        print(f"  {k}: {v}s")
