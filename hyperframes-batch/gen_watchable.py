#!/usr/bin/env python3
"""Watchable-video builder v3. Fixes: (1) background must MOVE and CHANGE per scene — every scene
gets its OWN animated visual (real-data candlesticks for CC / rotating pose+cutaway for Aurea /
animated data-viz for AE/QY), no single static backdrop; (2) 3-layer separation (voiceover / short
rolling captions / illustrative visual). Deterministic (no Math.random / Date; index-seeded PRNG).
Renderer: HyperFrames standalone composition, GSAP timeline window.__timelines["main"].
"""
import base64, html, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
CAPDIR = os.path.join(HERE, "captures")

BRAND = {
    "AE": dict(accent="#8B5CFF", accent2="#C6FF3A", bg1="#140a2b", bg2="#050409", name="AIRDROP EDGE", fn="→ Nina"),
    "CC": dict(accent="#38BDF8", accent2="#22d3ee", bg1="#07192f", bg2="#04070d", name="CLEAR CHARTS", fn="→ Nina"),
    "QY": dict(accent="#F5B301", accent2="#C6FF3A", bg1="#241905", bg2="#0a0803", name="QUIET YIELD", fn="→ Xaue"),
    "AU": dict(accent="#C6FF3A", accent2="#8B5CFF", bg1="#16240a", bg2="#070a04", name="AUREA", fn="→ Nina / Xaue"),
}
SERIF = '"Hoefler Text","Baskerville","Iowan Old Style",Georgia,serif'
SANS = '"Avenir Next","Helvetica Neue","Segoe UI",sans-serif'
MONO = '"SF Mono","Menlo",ui-monospace,monospace'
CJK_SANS = '"PingFang TC","PingFang SC","Noto Sans TC","Microsoft JhengHei",sans-serif'
COIN = {"CC-1": "ethereum", "CC-2": "bitcoin", "CC-3": "bitcoin", "CC-4": "bitcoin"}
EASES = ["power3.out", "power2.out", "expo.out", "back.out(1.4)"]
DIRS = [("y", 46), ("y", 46), ("y", 40), ("x", -64), ("x", 64)]   # no 'scale' entry -> no shrunk-entry frame
UP, DN = "#28d17f", "#ff5b6a"


def esc(s):
    return html.escape((s or "").strip())


def rng(seed):
    st = [(seed * 1103515245 + 12345) & 0x7FFFFFFF]
    def nxt(m):
        st[0] = (st[0] * 1103515245 + 12345) & 0x7FFFFFFF
        return st[0] % m
    return nxt


HERO_RE = re.compile(r"(\$|\+|-|~)?\s*([\d][\d,\.]*)\s*(%|x|X|B|M|K|bn)?", re.I)


_TIMEUNIT = re.compile(r"^[\s\-]*(month|mo|day|week|wk|year|yr|hour|hr|min|minute|second|sec)s?\b", re.I)


def hero_number(text):
    text = text or ""
    cands = []
    for m in HERO_RE.finditer(text):
        num = m.group(2).replace(",", "").strip(".")   # drop sentence-end dot ("2026." -> "2026")
        if not num or num == ".":
            continue
        try:
            val = float(num)
        except ValueError:
            continue
        if val == 0:
            continue
        pre, suf = (m.group(1) or ""), (m.group(3) or "")
        if val < 4 and not suf and not pre:
            continue
        # skip time-span qualifiers ("5-month high", "90 days", "12-month") — not a metric
        if not suf and _TIMEUNIT.match(text[m.end():]):
            continue
        # skip bare recent years ("Feb 2026", "of 2025") rendered as a giant meaningless count-up
        if not suf and not pre and "." not in num and len(num) == 4 and 2018 <= val <= 2035:
            continue
        cands.append((pre, val, suf, 1 if "." in num else 0))
    if not cands:
        return None
    # PREFER a real metric (has $/~ prefix or %/x/B/M/K suffix) over a bare incidental integer
    # (kills the giant stray "4" when a "$90.7B"/"70.4%" is present in the same line).
    for c in cands:
        if c[0] or c[2]:
            return c
    return cands[0]
    return None


def clean_text(t):
    """Normalize source copy: strip literal \\n, add missing space after punctuation (not between
    digits), collapse whitespace."""
    t = (t or "").replace("\\n", " ").replace("\n", " ").replace("\\", " ")
    t = re.sub(r"([,.;:!?，。；:！？])(?=[^\s\d])", r"\1 ", t)   # space after punct unless a digit follows
    return " ".join(t.split())


_PLACEHOLDER = re.compile(
    r"(?i)("
    r"cover\s*/|/\s*hook|hook\.?frame|\bcta\b\s*/|save\s*prompt|placeholder|^test\s+\w+$"
    r"|^close\s*\+?\s*cta|^open\s*\+?\s*hook|^recap\b|^outro\b|^intro\b|^cover\b|^beat\s*\d+"
    r"|^fact\s*\d+\b|^point\s+(one|two|three|four|five|six|seven|\d+)\b"
    r"|^(state|set|frame|reinforce|establish|tease|introduce)\s+the\b"
    r"|^invite\s+(the|to)\b|\bfact[-\s]?drop\b|\d+[-\s]?second\s+explainer|^promise\s+a\b"
    r"|\bmental\s+model$|\bexpectation$|anti[- ]?hype\s+explainer"
    r")"
)


def is_placeholder(t):
    return bool(_PLACEHOLDER.search((t or "").strip()))


def drop_placeholders(text):
    """Remove placeholder CLAUSES embedded anywhere in real copy (handles comma-clauses like
    'Test two, real counterparties.') — cleans both the TTS narration and the captions."""
    text = clean_text(text)
    # strip trailing authoring/CTA directives like 'Full breakdown -> link sticker + bio'
    text = re.sub(r"(?i)\s*[-–—>→]{1,3}\s*[^。.!?！？]*?(link\s*sticker|link\s*in\s*bio|\bbio\b|profile|個人檔案|個人簡介|檔案|主頁|首頁|連結|簡介).*$", "", text).strip()
    parts = re.split(r"([。.!?！？,，、;；:：]+\s*)", text)   # keep delimiters
    out, i = [], 0
    while i < len(parts):
        c = parts[i].strip()
        delim = parts[i + 1] if i + 1 < len(parts) else ""
        if c and not is_placeholder(c):
            out.append(c + delim)
        i += 2
    return clean_text("".join(out)) or text


_OPEN, _CLOSE = "「『（(《【", "」』）)》】"


def chunk_caption(narration, is_cjk):
    """Clause-complete captions: split ONLY at sentence/clause punctuation and NEVER inside a
    bracket pair or a Latin word. Merge tiny fragments; drop unmatched brackets. Each returned
    line is a complete, self-contained clause — eliminates orphan words / broken 「」 splits."""
    text = clean_text(narration)
    if not text or is_placeholder(text):
        return []
    clauses, buf, depth, ntext = [], "", 0, len(text)
    for idx, ch in enumerate(text):
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            depth = max(0, depth - 1)
        buf += ch
        if depth == 0 and ch in "。.!?！？；;，,、—:：":
            # NEVER split inside a number/date: . , : between two digits (keep $63.6B, 8,830, 3:1)
            pd = idx > 0 and text[idx - 1].isdigit()
            nd = idx + 1 < ntext and text[idx + 1].isdigit()
            # a comma date/number "July 22, 2026" or "1, 234": digit , [space] digit -> keep together
            if ch in ",，" and pd and not nd:
                j = idx + 1
                while j < ntext and text[j] == " ":
                    j += 1
                nd = j < ntext and text[j].isdigit()
            if ch in ".,:：，" and pd and nd:
                continue
            clauses.append(buf); buf = ""
    if buf.strip():
        clauses.append(buf)

    def units(s):
        return len(s) if is_cjk else len(s.split())
    lines = []
    for c in clauses:
        c = c.strip(" ，、,.。；;：:—-　").strip()
        if not c or is_placeholder(c):
            continue
        if re.fullmatch(r"(?i)(one|two|three|four|five|six|seven|eight|nine|\d{1,2})[.)、:：]?", c):
            continue   # drop a lone enumerator word ('Two') left over from 'Two: ...' splits
        # only merge a TINY CURRENT clause onto the previous line (never merge a full next clause
        # into a short previous line -> that produced run-on 'One didn't The difference')
        if lines and units(c) < (3 if is_cjk else 2):
            sep = "" if is_cjk else " "
            lines[-1] = (lines[-1] + sep + c).strip()
        else:
            lines.append(c)
    out = []
    for l in lines:
        for o, c in (("「", "」"), ("『", "』"), ("（", "）"), ("(", ")")):
            if l.count(o) != l.count(c):
                l = l.replace(o, "").replace(c, "")
        l = l.strip()
        if l:
            out.append(l)
    # EN: cap by words (safe at spaces, no lone 1-word tail). CJK: DON'T python-split (that produced
    # mid-word cuts like '助'/'理接進來'); keep the whole clause and let CSS wrap it by character.
    if is_cjk:
        return out[:6]
    wrapped = []
    MAX = 11
    for l in out:
        w = l.split()
        if len(w) <= MAX:
            wrapped.append(l); continue
        while len(w) > MAX:
            take = MAX - 1 if len(w) - MAX == 1 else MAX   # no lone 1-word tail
            wrapped.append(" ".join(w[:take])); w = w[take:]
        if w:
            wrapped.append(" ".join(w))
    return wrapped[:6]


def _label(head, is_cjk, limit=72):
    h = clean_text(head)
    if is_placeholder(h):
        return ""
    if len(h) <= limit:
        return h
    # list-y headline (·|｜/) -> keep the leading complete segments, never clip mid-word
    for sep in ("·", "｜", "|", " / "):
        if sep in h:
            acc = ""
            for p in [x.strip() for x in h.split(sep) if x.strip()]:
                if acc and len(acc) + len(p) + 3 > limit:
                    break
                acc = f"{acc} {sep} {p}" if acc else p
            if acc:
                return acc
    cut = h[:limit]
    for sep in ("。", ". ", "! ", "? ", "，", ", ", "、", " "):
        idx = cut.rfind(sep)
        if idx > limit * 0.5:
            return cut[:idx].strip()
    return cut.strip()


def _fit(text, is_cjk, big, mid, small):
    n = len(text or "")
    if is_cjk:
        return big if n <= 9 else (mid if n <= 16 else small)
    return big if n <= 20 else (mid if n <= 38 else small)


def _uri(path):
    ext = os.path.splitext(path)[1].lstrip(".").lower() or "png"
    ext = "jpeg" if ext == "jpg" else ext
    return f"data:image/{ext};base64," + base64.b64encode(open(path, "rb").read()).decode()


def _fetch_ohlc(coin, path):
    """Self-heal the OHLC cache from CoinGecko's free API (no auth). Pre-render data prep in Python
    (NOT an in-composition fetch), so it refreshes live candles without breaking Chrome determinism."""
    import urllib.request
    url = f"https://api.coingecko.com/api/v3/coins/{coin}/ohlc?vs_currency=usd&days=30"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "matrix-loop/1.0", "accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        if isinstance(data, list) and len(data) >= 10:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            json.dump(data, open(path, "w"))
            return data
    except Exception:
        pass
    return None


def _ohlc(pid):
    coin = COIN.get(pid)
    if not coin and (pid or "").upper().startswith("CC"):
        # generated CC clips (CC-gen-<hash>) have no fixed mapping -> deterministic coin by hash
        coin = ("bitcoin", "ethereum", "solana")[sum(ord(c) for c in pid) % 3]
    if not coin:
        return None
    p = os.path.join(CAPDIR, f"ohlc_{coin}.json")
    if os.path.exists(p):
        try:
            return json.load(open(p))
        except Exception:
            pass
    return _fetch_ohlc(coin, p)   # cache miss -> fetch live from CoinGecko


def _candles(ohlc, i, n, st, du, b):
    """Real-data candlestick that draws in left->right + gentle pan; window advances per scene."""
    win = 46
    L = len(ohlc)
    start = 0 if L <= win else int((L - win) * (i / max(1, n - 1)))
    seg = ohlc[start:start + win]
    lo = min(c[3] for c in seg); hi = max(c[2] for c in seg); span = (hi - lo) or 1
    VW, VH, pad = 1080, 900, 60
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
        parts.append(f'<line class="cd cd{i}" x1="{x}" y1="{yy(h)}" x2="{x}" y2="{yy(l)}" stroke="{col}" stroke-width="2.2"/>')
        parts.append(f'<rect class="cd cd{i}" x="{round(x - bw / 2, 1)}" y="{bt}" width="{round(bw, 1)}" height="{round(max(3, bb - bt), 1)}" rx="1.5" fill="{col}"/>')
    last = yy(seg[-1][4])
    # trader annotations (点位/失效位): recent swing resistance + invalidation, drawn from the data
    tail = seg[-12:] if len(seg) >= 12 else seg
    r_hi = max(c[2] for c in tail); r_lo = min(c[3] for c in tail)

    def _fmt(p):
        if p >= 1e6:
            return f"${p/1e6:.2f}M"
        if p >= 1000:
            return f"${p/1000:.1f}K"
        return f"${p:,.2f}"
    WARN = "#F5B301"
    yhi, ylo = yy(r_hi), yy(r_lo)
    ann = (
        f'<line class="an{i}" x1="0" y1="{yhi}" x2="{VW}" y2="{yhi}" stroke="{WARN}" stroke-width="2" opacity="0.85"/>'
        f'<text class="an{i}" x="{VW-18}" y="{max(28,yhi-10)}" fill="{WARN}" font-size="27" font-weight="700" '
        f'font-family=\'{SANS}\' text-anchor="end">阻力 {_fmt(r_hi)}</text>'
        f'<line class="an{i}" x1="0" y1="{ylo}" x2="{VW}" y2="{ylo}" stroke="{DN}" stroke-width="2" stroke-dasharray="11 8" opacity="0.85"/>'
        f'<text class="an{i}" x="{VW-18}" y="{min(VH-14,ylo+34)}" fill="{DN}" font-size="27" font-weight="700" '
        f'font-family=\'{SANS}\' text-anchor="end">失效位 {_fmt(r_lo)}</text>'
    )
    svg = (f'<svg viewBox="0 0 {VW} {VH}" preserveAspectRatio="xMidYMid slice" style="width:112%;height:100%">'
           f'<line class="pl{i}" x1="0" y1="{last}" x2="{VW}" y2="{last}" stroke="{b["accent"]}" stroke-width="2.5" stroke-dasharray="9 11" opacity="0.55"/>'
           + "".join(parts) + ann + "</svg>")
    tw = [
        f'tl.fromTo(".cd{i}",{{opacity:0,y:26}},{{opacity:1,y:0,duration:0.9,ease:"power2.out",stagger:{round(0.7 / len(seg), 4)}}},{round(st + 0.2, 2)});',
        f'gsap.set(".pl{i}",{{transformOrigin:"0% 50%"}});tl.fromTo(".pl{i}",{{scaleX:0}},{{scaleX:1,duration:0.9,ease:"power2.out"}},{round(st + 0.7, 2)});',
        f'tl.fromTo(".an{i}",{{opacity:0}},{{opacity:1,duration:0.5,ease:"power1.out"}},{round(st + 1.1, 2)});',
        f'tl.fromTo("#ch{i}",{{x:-46}},{{x:30,duration:{du},ease:"none"}},{st});',
    ]
    return f'<div class="chart" id="ch{i}">{svg}</div>', tw


def _area(ohlc, i, n, st, du, b):
    """Area/line chart of close prices that DRAWS in left->right."""
    win = 50
    L = len(ohlc); start = 0 if L <= win else int((L - win) * (i / max(1, n - 1)))
    seg = ohlc[start:start + win]; cl = [c[4] for c in seg]
    lo, hi = min(cl), max(cl); span = (hi - lo) or 1
    VW, VH, pad = 1080, 900, 70

    def X(k):
        return round(pad + k * (VW - 2 * pad) / max(1, len(cl) - 1), 1)

    def Y(p):
        return round(pad + (hi - p) / span * (VH - 2 * pad), 1)
    pts = " ".join(f"{X(k)},{Y(v)}" for k, v in enumerate(cl))
    col = UP if cl[-1] >= cl[0] else DN
    apts = f"{X(0)},{VH - pad} " + pts + f" {X(len(cl) - 1)},{VH - pad}"
    svg = (f'<svg viewBox="0 0 {VW} {VH}" preserveAspectRatio="xMidYMid slice" style="width:110%;height:100%">'
           f'<defs><linearGradient id="ag{i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{col}" stop-opacity="0.5"/><stop offset="1" stop-color="{col}" stop-opacity="0"/></linearGradient></defs>'
           f'<polygon class="ar{i}" points="{apts}" fill="url(#ag{i})" opacity="0"/>'
           f'<polyline class="ln{i}" points="{pts}" fill="none" stroke="{col}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    tw = [
        f'(function(){{var e=document.querySelector(".ln{i}");if(e){{var L=e.getTotalLength();gsap.set(e,{{strokeDasharray:L,strokeDashoffset:L}});tl.to(e,{{strokeDashoffset:0,duration:1.5,ease:"power2.out"}},{round(st + 0.2, 2)});}}}})();',
        f'tl.to(".ar{i}",{{opacity:1,duration:0.9,ease:"power2.out"}},{round(st + 1.0, 2)});',
        f'tl.fromTo("#ch{i}",{{x:-28}},{{x:22,duration:{du},ease:"none"}},{st});',
    ]
    return f'<div class="chart" id="ch{i}">{svg}</div>', tw


def _bars(ohlc, i, n, st, du, b):
    """Period-over-period % change bars (real derived data) growing from a mid axis."""
    win = 38
    L = len(ohlc); start = 0 if L <= win else int((L - win) * (i / max(1, n - 1)))
    seg = ohlc[start:start + win]
    rets = [((seg[k][4] - seg[k - 1][4]) / seg[k - 1][4] * 100 if seg[k - 1][4] else 0) for k in range(1, len(seg))]
    mx = max(1.0, max(abs(r) for r in rets)); VW, VH, pad = 1080, 900, 90
    mid = VH / 2; bw = (VW - 2 * pad) / len(rets)
    parts = [f'<line x1="0" y1="{mid}" x2="{VW}" y2="{mid}" stroke="#ffffff26" stroke-width="2"/>']
    for k, r in enumerate(rets):
        x = round(pad + k * bw, 1); h = max(3, round(abs(r) / mx * (VH / 2 - pad), 1))
        col = UP if r >= 0 else DN; y = round(mid - h, 1) if r >= 0 else round(mid, 1)
        parts.append(f'<rect class="br{i}" x="{x}" y="{y}" width="{round(bw * 0.66, 1)}" height="{h}" rx="2" fill="{col}"/>')
    svg = (f'<svg viewBox="0 0 {VW} {VH}" preserveAspectRatio="xMidYMid slice" style="width:108%;height:100%">'
           + "".join(parts) + "</svg>")
    tw = [
        f'gsap.set(".br{i}",{{transformBox:"fill-box",transformOrigin:"50% 50%"}});'
        f'tl.fromTo(".br{i}",{{scaleY:0,opacity:0}},{{scaleY:1,opacity:1,duration:0.7,ease:"power2.out",stagger:{round(0.5 / max(1, len(rets)), 4)}}},{round(st + 0.2, 2)});',
        f'tl.fromTo("#ch{i}",{{x:-22}},{{x:18,duration:{du},ease:"none"}},{st});',
    ]
    return f'<div class="chart" id="ch{i}">{svg}</div>', tw


CC_FORMS = [_candles, _area, _bars]


def build_watchable(pkg, spans, captions, assets):
    pre = pkg["id"].split("-")[0]
    pid = pkg["id"]
    b = BRAND[pre]
    is_cjk = pkg.get("language", "").startswith("繁")
    scenes = pkg.get("scenes") or []
    n = len(scenes)
    total = round((spans[-1][0] + spans[-1][1]) if spans else 6, 2) + 0.25
    head_font = CJK_SANS if is_cjk else SERIF
    body = CJK_SANS if is_cjk else SANS
    ohlc = _ohlc(pid)

    scene_bg = (f"radial-gradient(130% 80% at 78% -6%,{b['accent']}2b,transparent 55%),"
                f"radial-gradient(105% 72% at -8% 108%,{b['accent2']}20,transparent 55%),"
                f"linear-gradient(165deg,{b['bg1']},{b['bg2']})")
    clips, tw = [], []
    for i, (s, (st, du)) in enumerate(zip(scenes, spans)):
        r = rng(i * 97 + 13)
        ease = EASES[r(len(EASES))]
        dax, dv = DIRS[r(len(DIRS))]
        bin_ = round(st + 0.16, 2); bout = round(st + du - 0.3, 2)
        head = _label(s.get("onScreenCaption"), is_cjk)
        asset = assets.get(i)
        # ---- per-scene VISUAL (always moving, changes each scene) ----
        vis_html, vis_tw = "", []
        content, ctw = "", []
        content_low = True   # image/chart/host scenes anchor text low; data/quote centers (set below)
        if isinstance(asset, dict) and os.path.exists(asset.get("path", "")):
            uri = _uri(asset["path"])
            zoom = 1.02 + 0.02 * r(3)
            dx = [-40, 36, -28, 30][r(4)]; dy = [24, -20, 30, -16][r(4)]
            objp = "50% 14%" if pre == "AU" else "50% 42%"
            vis_html = (f'<div class="vis"><img class="kbimg" id="kb{i}" src="{uri}" style="object-position:{objp}"/>'
                        f'<div class="scrim"></div></div>')
            vis_tw = [f'gsap.set("#kb{i}",{{transformOrigin:"50% 40%"}});'
                      f'tl.fromTo("#kb{i}",{{scale:{round(zoom,3)},x:{dx},y:{dy}}},{{scale:{round(zoom+0.14,3)},x:{-dx//2},y:{-dy//2},duration:{du},ease:"none"}},{st});']
            content, ctw = _overlay_label(i, head, st, b, is_cjk, head_font)
        elif ohlc and pre == "CC":
            vh, vt = CC_FORMS[i % len(CC_FORMS)](ohlc, i, n, st, du, b)
            vis_html = f'<div class="vis vgrid">{vh}<div class="scrim"></div></div>'
            vis_tw = vt
            content, ctw = _overlay_label(i, head, st, b, is_cjk, head_font)
        else:
            # data/quote: bright moving mesh (3 blobs + drifting grid), content CENTERED — never empty black
            content_low = False
            vis_html = (f'<div class="vis mesh"><div class="blob bA" id="ba{i}"></div><div class="blob bB" id="bb{i}"></div>'
                        f'<div class="blob bC" id="bc{i}"></div><div class="ring" id="rg{i}"></div><div class="grid" id="gr{i}"></div></div>')
            rings = max(1, int(du / 6) + 1)
            vis_tw = [
                f'tl.fromTo("#ba{i}",{{xPercent:-34,yPercent:-18,scale:1}},{{xPercent:30,yPercent:22,scale:1.2,duration:{du},ease:"sine.inOut"}},{st});',
                f'tl.fromTo("#bb{i}",{{xPercent:30,yPercent:24,scale:1.18}},{{xPercent:-28,yPercent:-14,scale:1,duration:{du},ease:"sine.inOut"}},{st});',
                f'tl.fromTo("#bc{i}",{{xPercent:-12,yPercent:28,scale:1.1}},{{xPercent:24,yPercent:-22,scale:1.34,duration:{du},ease:"sine.inOut"}},{st});',
                f'gsap.set("#rg{i}",{{transformOrigin:"50% 50%"}});tl.to("#rg{i}",{{rotation:360,duration:6,ease:"none",repeat:{rings}}},{st});',
                f'tl.fromTo("#gr{i}",{{yPercent:0}},{{yPercent:-8,duration:{du},ease:"none"}},{st});',
            ]
            content, ctw = _overlay_data(i, s, head, st, du, b, is_cjk, head_font, r)
        caps_html, caps_tw = _captions(i, captions.get(i, []), st, du, b, is_cjk)
        dots = "".join(chr(9679) if j == i else chr(9675) for j in range(n))
        clips.append(
            f'\n  <section id="s{i}" class="clip scene" data-start="{st}" data-duration="{du}" data-track-index="1" style="background:{scene_bg}">'
            f'{vis_html}'
            f'<div class="chrome"><span class="chip">{esc(b["name"])}</span><span class="fn">{esc(b["fn"])}</span></div>'
            f'<div id="in{i}" class="in {"low" if content_low else "mid"}">{content}</div>{caps_html}'
            f'<div class="foot"><span class="dots">{dots}</span><span class="nfa">NFA</span></div></section>')
        # entrance / exit handoff of the content layer (visual keeps moving underneath)
        # gentle entrance only; NO exit fade (HyperFrames clips are hard-adjacent, so fading the
        # outgoing content left a ~0.3s blank/letterboxed boundary frame — keep content full to the cut)
        tw.append(f'tl.fromTo("#in{i}",{{autoAlpha:0,{dax}:{dv}}},{{autoAlpha:1,{dax}:0,duration:0.45,ease:"{ease}"}},{bin_});')
        tw.extend(vis_tw); tw.extend(ctw); tw.extend(caps_tw)

    doc = f"""<!doctype html>
<html lang="{'zh-Hant' if is_cjk else 'en'}" data-resolution="portrait">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1080px;height:1920px;overflow:hidden;background:#04060c;font-family:{body};-webkit-font-smoothing:antialiased}}
#root{{position:relative;width:1080px;height:1920px;overflow:hidden;background:#04060c}}
.scene{{position:absolute;inset:0;overflow:hidden}}
.vis{{position:absolute;inset:0;overflow:hidden}}
.vgrid{{background:radial-gradient(120% 80% at 50% 0%,{b['accent']}12,transparent 60%)}}
.kbimg{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;will-change:transform}}
.chart{{position:absolute;left:-6%;right:-6%;top:120px;bottom:120px;width:112%}}
.scrim{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(4,6,12,.42) 0%,rgba(4,6,12,.30) 34%,rgba(4,6,12,.44) 52%,rgba(4,6,12,.62) 70%,rgba(4,6,12,.95) 100%)}}
.blob{{position:absolute;width:820px;height:820px;border-radius:50%;filter:blur(64px);opacity:.72;will-change:transform}}
.bA{{left:-180px;top:60px;background:radial-gradient(circle,{b['accent']}99,transparent 68%)}}
.bB{{right:-220px;bottom:20px;background:radial-gradient(circle,{b['accent2']}82,transparent 68%)}}
.bC{{left:28%;top:34%;width:640px;height:640px;background:radial-gradient(circle,{b['accent']}66,transparent 70%)}}
.grid{{position:absolute;inset:-12% 0;background-image:linear-gradient(#ffffff12 1px,transparent 1px),linear-gradient(90deg,#ffffff12 1px,transparent 1px);background-size:72px 72px;opacity:.55;will-change:transform}}
.ring{{position:absolute;left:50%;top:40%;width:920px;height:920px;margin:-460px 0 0 -460px;border-radius:50%;background:conic-gradient(from 0deg,{b['accent']}00,{b['accent']}55 12%,{b['accent']}00 32%,{b['accent2']}44 60%,{b['accent']}00 82%);opacity:.42;filter:blur(16px);will-change:transform}}
.chrome{{position:absolute;top:96px;left:90px;right:90px;display:flex;justify-content:space-between;align-items:center;z-index:6}}
.chip{{font-family:{MONO};font-weight:700;letter-spacing:.14em;font-size:26px;color:{b['accent']};border:2px solid {b['accent']}55;border-radius:999px;padding:9px 22px;backdrop-filter:blur(4px)}}
.fn{{font-family:{MONO};font-size:24px;color:#ffffffcc}}
.in{{position:absolute;left:0;right:0;top:0;bottom:0;display:flex;flex-direction:column;z-index:4}}
.in.low{{justify-content:flex-end;padding:150px 88px 400px}}
.in.mid{{justify-content:center;padding:210px 82px 300px}}
.kicker{{font-family:{MONO};font-size:26px;letter-spacing:.24em;color:{b['accent']};margin-bottom:18px;text-transform:uppercase}}
.head{{font-family:{head_font};color:#fff;font-weight:800;line-height:1.06;letter-spacing:-0.01em;text-shadow:0 4px 34px rgba(0,0,0,.9)}}
.rule{{width:110px;height:7px;border-radius:7px;margin-top:28px;background:linear-gradient(90deg,{b['accent']},{b['accent']}11)}}
.statnum{{font-family:{MONO};font-weight:800;font-variant-numeric:tabular-nums slashed-zero;color:#fff;line-height:.9;letter-spacing:-0.02em;text-shadow:0 6px 40px rgba(0,0,0,.9)}}
.statbar{{height:20px;border-radius:11px;background:#ffffff1c;overflow:hidden;margin-top:34px;max-width:840px}}
.statbar>i{{display:block;height:100%;width:100%;transform:scaleX(0);transform-origin:left;background:linear-gradient(90deg,{b['accent']},{b['accent2']});border-radius:11px}}
.statlab{{font-family:{body};font-weight:600;color:#eef1f7;font-size:40px;margin-top:26px;max-width:860px;line-height:1.28;text-shadow:0 3px 20px rgba(0,0,0,.85)}}
.caps{{position:absolute;left:60px;right:60px;bottom:196px;height:170px;display:flex;align-items:center;justify-content:center;z-index:7}}
.cap{{position:absolute;left:0;right:0;text-align:center;opacity:0;padding:0 44px}}
.capt{{display:inline-block;font-family:{head_font};font-weight:800;font-size:{'54px' if is_cjk else '50px'};color:#fff;line-height:1.28;padding:12px 26px;border-radius:16px;background:rgba(4,6,12,.62);box-decoration-break:clone;-webkit-box-decoration-break:clone;word-break:normal;overflow-wrap:break-word;max-width:940px;text-shadow:0 2px 12px rgba(0,0,0,.9)}}
.foot{{position:absolute;left:90px;right:90px;bottom:104px;display:flex;justify-content:space-between;align-items:center;z-index:6}}
.dots{{letter-spacing:10px;color:{b['accent']};font-size:20px}}
.nfa{{font-family:{MONO};font-size:22px;color:#ffffff66;letter-spacing:.12em}}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-fps="30" data-width="1080" data-height="1920">{''.join(clips)}
</div>
<script>
window.__timelines=window.__timelines||{{}};
var tl=gsap.timeline({{paused:true}});
{chr(10).join(tw)}
window.__timelines["main"]=tl;
</script>
</body></html>"""
    return doc, total


def _overlay_label(i, head, st, b, is_cjk, head_font):
    fs = _fit(head, is_cjk, 82, 66, 52)
    return (f'<div class="kicker">{esc(b["name"].split()[0])}</div>'
            f'<div class="head" style="font-size:{fs}px">{esc(head)}</div><div class="rule"></div>'), [
        f'tl.fromTo("#in{i} .rule",{{scaleX:0}},{{scaleX:1,duration:0.5,ease:"power3.out"}},{round(st + 0.4, 2)});']


def _overlay_data(i, s, head, st, du, b, is_cjk, head_font, r):
    hn = hero_number(s.get("onScreenCaption")) or hero_number(s.get("narration", ""))
    if hn:
        pre, val, suf, dec = hn
        fmt = f"{val:.1f}" if dec else f"{int(val)}"
        size = 320 if len(fmt) <= 3 else (250 if len(fmt) <= 5 else 200)
        frac = min(1.0, val / 100.0) if suf == "%" else 0.8
        lab = _label(s.get("onScreenCaption"), is_cjk, 64)
        html_ = (f'<div class="kicker">{esc(b["name"].split()[0])}</div>'
                 f'<div class="statnum" id="st{i}" style="font-size:{size}px">{pre}0{suf}</div>'
                 f'<div class="statbar"><i id="sb{i}"></i></div>'
                 f'<div class="statlab">{esc(lab)}</div>')
        cdur = round(min(2.4, max(1.4, du * 0.28)), 2)   # punchy count-up: LANDS early (<=2.4s) then holds
                                                          # (was du*0.55 -> ran ~6s on long scenes, number read "wrong" most of the scene)
        tw = [
            f'var o{i}={{v:0}};tl.to(o{i},{{v:{val},duration:{cdur},ease:"power1.inOut",'
            f'onUpdate:function(){{document.getElementById("st{i}").textContent="{pre}"+({dec}?o{i}.v.toFixed(1):Math.round(o{i}.v))+"{suf}";}}}},{round(st + 0.3, 2)});',
            f'tl.to("#sb{i}",{{scaleX:{round(frac, 3)},duration:{cdur},ease:"power1.inOut"}},{round(st + 0.35, 2)});',
            f'tl.to("#st{i}",{{scale:1.06,duration:0.18,ease:"back.out(2)"}},{round(st + 0.3 + cdur, 2)});'
            f'tl.to("#st{i}",{{scale:1,duration:0.4,ease:"power2.out"}},{round(st + 0.5 + cdur, 2)});',
        ]
        return html_, tw
    fs = _fit(head, is_cjk, 96, 74, 58)
    return (f'<div class="kicker">{esc(b["name"].split()[0])}</div>'
            f'<div class="head" style="font-size:{fs}px">{esc(head)}</div><div class="rule"></div>'), [
        f'tl.fromTo("#in{i} .rule",{{scaleX:0}},{{scaleX:1,duration:0.5,ease:"power3.out"}},{round(st + 0.4, 2)});']


def _captions(i, chunks, st, du, b, is_cjk):
    if not chunks:
        return "", []
    ws = st + 0.15; win = max(0.6, du - 0.4); per = win / len(chunks)
    parts, tw = [], []
    for k, c in enumerate(chunks):
        cid = f"c{i}_{k}"; cs = round(ws + k * per, 2); ce = round(cs + per, 2)
        parts.append(f'<div id="{cid}" class="cap"><span class="capt">{esc(c)}</span></div>')
        tw.append(f'tl.fromTo("#{cid}",{{autoAlpha:0,y:24}},{{autoAlpha:1,y:0,duration:0.18,ease:"power2.out"}},{cs});')
        # fully hidden BEFORE the next chunk appears -> no two captions on screen at once
        tw.append(f'tl.to("#{cid}",{{autoAlpha:0,duration:0.12,ease:"power1.in"}},{round(ce - 0.18, 2)});')
    return f'<div class="caps">{"".join(parts)}</div>', tw
