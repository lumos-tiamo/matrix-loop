#!/usr/bin/env python3
"""Watchable producer (v2): package -> trim(40-90s) -> per-scene TTS -> audio-timed spans ->
rolling karaoke captions -> pick illustrative asset -> build_watchable HTML -> render -> mux voice.
Usage: backend/.venv/bin/python produce2.py CC-1 AU-1 [--quality=draft]
"""
import asyncio, json, os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen_watchable import build_watchable, hero_number, chunk_caption, clean_text, is_placeholder, drop_placeholders  # noqa: E402
from preflight import check_package, blockers  # noqa: E402

PKGS = {p["id"]: p for p in json.load(open("/Users/aa00102/matrix-loop/_content_packages_2026-07-16.json"))["packages"]}
OUT_DIR = "/Users/aa00102/matrix-loop/backend/data/videos"
COMP_DIR = os.path.join(HERE, "compositions")
MAT = os.path.join(HERE, "material")
CAP = os.path.join(HERE, "captures")
DESK = "/Users/aa00102/Desktop/私域矩阵_视频生产"
for d in (OUT_DIR, COMP_DIR, MAT, CAP):
    os.makedirs(d, exist_ok=True)

VOICE = {"AE": "en-US-GuyNeural", "CC": "en-US-EricNeural", "QY": "en-US-AriaNeural", "AU": "zh-TW-HsiaoChenNeural"}
DAYDIR = {"AE": "01_AirdropEdge_X", "CC": "02_ClearCharts_X", "QY": "03_QuietYield_IG", "AU": "04_Aurea_TikTok"}
PAUSE = 0.30
QUALITY = "draft"


def ffdur(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", p],
                       capture_output=True, text=True)
    return float(o.stdout.strip() or 0)


async def _synth(text, voice, mp3):
    import edge_tts
    c = edge_tts.Communicate(text, voice)
    with open(mp3, "wb") as f:
        async for ch in c.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])


def _split_sentences(nar):
    """Decimal-safe sentence split: a '.' ends a sentence ONLY when it is not part of a number
    (prev char not a digit) AND is followed by whitespace/end — so '$90.7 billion' / '$84.6B'
    stay intact. 。！？!? always end a sentence. Punctuation stays attached to its sentence."""
    out, buf, i, n = [], [], 0, len(nar)
    while i < n:
        ch = nar[i]
        buf.append(ch)
        boundary = False
        if ch in "。！？!?":
            boundary = True
        elif ch == ".":
            prev = nar[i - 1] if i > 0 else ""
            nxt = nar[i + 1] if i + 1 < n else ""
            if not prev.isdigit() and (nxt == "" or nxt.isspace()):
                boundary = True
        if boundary:
            j = i + 1
            while j < n and nar[j].isspace():
                j += 1
            s = "".join(buf).strip()
            if s:
                out.append(s)
            buf = []
            i = j
            continue
        i += 1
    s = "".join(buf).strip()
    if s:
        out.append(s)
    return out


def shorten(nar, is_cjk, max_units=None):
    """Keep only WHOLE sentences up to a budget (never a dangling mid-sentence fragment)."""
    nar = clean_text(nar)
    if not nar:
        return nar
    max_units = max_units or (72 if is_cjk else 30)   # CJK budget up so Aurea clips clear ~45s
    sents = [s.strip() for s in _split_sentences(nar) if s.strip()]
    out, tot = [], 0
    for s in sents:
        u = len(s) if is_cjk else len(s.split())
        if out and tot + u > max_units:
            break
        out.append(s); tot += u
    return " ".join(out).strip() or nar


def trim_pkg(pkg):
    is_cjk = pkg.get("language", "").startswith("繁")
    # sanitize: clean copy, drop placeholder/template scenes (Test two / CTA/save prompt / Cover.hook.Frame / \n)
    scenes = []
    for s in pkg.get("scenes") or []:
        oc = drop_placeholders(s.get("onScreenCaption", ""))
        nr = drop_placeholders(s.get("narration", ""))
        # hook/directive-only scenes: narration cleaned to nothing (e.g. "Cover / hook card…") ->
        # speak the on-screen headline so the scene isn't silent / doesn't leak a stray fragment.
        if (not nr or is_placeholder(nr)) and oc:
            nr = oc
        if not nr and not oc:
            continue
        s2 = dict(s); s2["onScreenCaption"] = oc; s2["narration"] = nr
        scenes.append(s2)
    if len(scenes) > 6:
        keep = {0, len(scenes) - 1}
        scored = sorted(((2 if hero_number(s.get("onScreenCaption", "")) else 0, i)
                         for i, s in enumerate(scenes)), reverse=True)
        for _, i in scored:
            if len(keep) >= 6:
                break
            keep.add(i)
        scenes = [scenes[i] for i in sorted(keep)]
    out = []
    for s in scenes:
        s2 = dict(s)
        s2["narration"] = shorten(s.get("narration", ""), is_cjk)
        out.append(s2)
    p2 = dict(pkg)
    p2["scenes"] = out
    return p2


def pick_assets(pid, pkg):
    """Per-scene visual so the background CHANGES + MOVES each scene:
      - AU: rotate through pose/expression images; cut to real Nina/data screenshots on relevant scenes
      - CC: leave to the real-data candlestick (builder), unless a real capture s{i}.png exists
      - AE/QY: per-scene capture if any; opener render on the hook scene; else animated data-viz
    """
    pre = pid.split("-")[0]
    assets = {}
    daydir = os.path.join(DESK, DAYDIR[pre])
    parts = pid.split("-")
    try:
        num = int(parts[1])
    except (IndexError, ValueError):
        num = 0   # on-demand / generated clips have no Day{NN} reference assets
    dd = os.path.join(daydir, f"Day{num:02d}", "参考图")
    capdir = os.path.join(CAP, pid)
    day_imgs = [os.path.join(dd, f) for f in sorted(os.listdir(dd))] if os.path.isdir(dd) else []
    day_imgs = [p for p in day_imgs if p.lower().endswith((".png", ".jpg", ".jpeg"))]
    cutaways = [p for p in day_imgs if "opener" not in os.path.basename(p)]
    opener = next((p for p in day_imgs if "opener" in os.path.basename(p)), None)

    def cap(i):
        p = os.path.join(capdir, f"s{i}.png")
        return p if os.path.exists(p) else None

    if pre == "AU":
        # ONLY the locked 2A persona (candidate-* are different people -> would break identity).
        # Alternate: consistent host scenes + animated 繁中 data/quote cards + real cutaways = motion+variety, one face.
        # ONLY the verified-clean locked 2A (candidate-* are different people; Day cutaways may carry
        # AI-gibberish text). Host on ~half the scenes, animated 繁中 data cards on the rest.
        host_p = os.path.join(daydir, "_AUREA_锁定形象_2A.png")
        host_p = host_p if os.path.exists(host_p) else None
        ns = len(pkg["scenes"])
        for i in range(ns):
            if cap(i):
                assets[i] = {"type": "image", "path": cap(i)}
            elif host_p and (i == 0 or i == ns - 1 or i % 2 == 0):
                assets[i] = {"type": "image", "path": host_p}
    elif pre == "CC":
        for i in range(len(pkg["scenes"])):
            if cap(i):
                assets[i] = {"type": "chart", "path": cap(i)}   # else -> candlestick in builder
    else:  # AE / QY -> animated data cards only (opener renders dropped: baked AI text like "QUIET FIELD")
        for i in range(len(pkg["scenes"])):
            if cap(i):
                assets[i] = {"type": "image", "path": cap(i)}
    return assets


def _progress(cb, stage, pct):
    if cb:
        try:
            cb(stage, pct)
        except Exception:
            pass


def _render_pkg(pid, pkg, voice, out, *, on_progress=None):
    """Core render: preflight -> per-scene TTS -> spans -> captions -> assets -> build -> render -> mux.
    `pid` is only a naming/asset-routing key (prefix picks brand+voice; num picks day assets).
    Returns the output mp4 path or None on a blocker / render failure."""
    # QUALITY GATE: never ship a package with a known defect class (directive leak, number split,
    # empty narration, banned fact). This is the anti-rework guard.
    iss = check_package(pkg)
    bl = blockers(iss)
    if bl:
        print(f"!! {pid} FAILED preflight ({len(bl)} blocker(s)) — not rendering:")
        for x in bl:
            print("     ", x)
        return None
    scenes = pkg["scenes"]
    is_cjk = (pkg.get("language", "") or "").startswith(("繁", "zh"))
    _progress(on_progress, "synth", 10)
    segs, durs = [], []
    for i, s in enumerate(scenes):
        seg = os.path.join(MAT, f"{pid}.seg{i}.mp3")
        asyncio.run(_synth(s.get("narration") or "…", voice, seg))
        segs.append(seg)
        durs.append(max(1.4, ffdur(seg)))
    spans, cur = [], 0.0
    for d in durs:
        spans.append((round(cur, 2), round(d + PAUSE, 2)))
        cur = round(cur + d + PAUSE, 2)
    captions = {i: chunk_caption(s.get("narration", ""), is_cjk) for i, s in enumerate(scenes)}
    assets = pick_assets(pid, pkg)

    voice_mp3 = os.path.join(MAT, f"{pid}.voice.mp3")
    sil = os.path.join(MAT, "_sil30.mp3")
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(PAUSE),
                    "-c:a", "libmp3lame", sil], capture_output=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as lf:
        for seg in segs:
            lf.write(f"file '{seg}'\nfile '{sil}'\n")
        listf = lf.name
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listf, "-c:a", "libmp3lame",
                    "-ar", "24000", voice_mp3], capture_output=True)

    _progress(on_progress, "compose", 40)
    doc, total = build_watchable(pkg, spans, captions, assets)
    comp = os.path.join(COMP_DIR, f"{pid}.html")
    open(comp, "w").write(doc)

    _progress(on_progress, "render", 55)
    silent = os.path.join(tempfile.gettempdir(), f"hf_{pid}.silent.mp4")
    env = dict(os.environ, HYPERFRAMES_SKIP_SKILLS="1")
    r = subprocess.run(["npx", "hyperframes", "render", ".", "-c", f"compositions/{pid}.html", "-o", silent, "-q", QUALITY],
                       cwd=HERE, env=env, capture_output=True, text=True)
    if not os.path.exists(silent):
        print(f"!! render failed {pid}:\n{r.stdout[-1200:]}\n{r.stderr[-400:]}")
        return None
    _progress(on_progress, "mux", 90)
    subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", voice_mp3, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "160k", "-shortest", out], capture_output=True)
    for seg in segs:
        try:
            os.remove(seg)
        except OSError:
            pass
    dur = ffdur(out)
    if not (35 <= dur <= 95):
        print(f"⚠ {pid}: duration {dur:.0f}s outside 40-90s target (shipped anyway)")
    _progress(on_progress, "done", 100)
    print(f"✓ {pid}: {len(scenes)} scenes · {dur:.0f}s · voice={voice} · assets={sorted(k for k in assets)} -> {out}")
    return out


def produce(pid):
    pre = pid.split("-")[0]
    out = os.path.join(OUT_DIR, f"hf_{pid}.mp4")
    return _render_pkg(pid, trim_pkg(PKGS[pid]), VOICE[pre], out)


_HL_TRAIL = {"a", "an", "the", "is", "are", "was", "were", "of", "to", "for", "and", "in", "on",
             "with", "that", "this", "your", "you", "it", "be", "as", "at", "by", "or", "but", "so",
             "into", "from", "than", "then", "just"}


def _headline(sent, is_cjk):
    """Punchy, COMPLETE headline from a sentence — never ends mid-phrase on an article/prep/copula
    (fixes '...five chains is a'). CJK: first clause capped; EN: first clause <=8 words, trailing
    weak words trimmed."""
    first = re.split(r"[，,。.!?！？;；:：—]|(?: - )", sent)[0].strip()
    if is_cjk:
        return first[:18]
    words = first.split()[:8]
    while words and words[-1].lower().strip(",.:;\"'") in _HL_TRAIL:
        words.pop()
    return " ".join(words) or first


def build_pkg_from_script(script_text, brand_prefix, language=None, headlines=None):
    """Turn an arbitrary adopted-script narration into a watchable package (for on-demand /
    autopilot generation). Splits into <=6 scenes on sentences; each scene's headline is a short
    key clause (or a supplied headline). Same downstream pipeline => same quality bar."""
    is_cjk = (language or "").startswith(("繁", "zh")) or brand_prefix == "AU"
    text = clean_text(drop_placeholders(script_text or ""))
    sents = [s.strip() for s in _split_sentences(text) if s.strip()]   # decimal-safe (keeps 4.5%/5.2%)
    if not sents:
        sents = [text or "…"]
    # group sentences into ~5-6 balanced scenes
    n = min(6, max(3, len(sents)))
    per = max(1, (len(sents) + n - 1) // n)
    groups = [sents[i:i + per] for i in range(0, len(sents), per)][:6]
    scenes = []
    for gi, g in enumerate(groups):
        nar = " ".join(g)
        hl = (headlines[gi] if headlines and gi < len(headlines) else None)
        if not hl:
            hl = _headline(g[0], is_cjk)
        scenes.append({"onScreenCaption": hl, "narration": nar})
    return {"id": f"{brand_prefix}-0", "language": language or ("繁中" if is_cjk else "en"), "scenes": scenes}


def produce_from_script(out_path, script_text, brand_prefix, *, language=None, on_progress=None):
    """Render a single video from raw adopted-script text to out_path. Used by the backend
    HyperframesProvider so the frontend 'generate video' button yields the SAME quality as the
    curated batch. Returns out_path or None."""
    pre = brand_prefix if brand_prefix in VOICE else "AE"
    pkg = trim_pkg(build_pkg_from_script(script_text, pre, language))
    # unique naming so concurrent generations don't collide
    import hashlib
    tag = hashlib.sha1((script_text or "").encode("utf-8")).hexdigest()[:10]
    pid = f"{pre}-gen-{tag}"
    return _render_pkg(pid, pkg, VOICE[pre], out_path, on_progress=on_progress)


def _optval(flag, default=None):
    """--flag=value or --flag value"""
    for i, a in enumerate(sys.argv[1:]):
        if a == flag and i + 2 <= len(sys.argv[1:]):
            return sys.argv[1:][i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return default


def main():
    global QUALITY
    QUALITY = _optval("--quality", QUALITY)   # accepts --quality=draft AND --quality draft
    # on-demand single render from raw script (backend HyperframesProvider shells here)
    if "--from-script" in sys.argv:
        brand = _optval("--brand", "AE")
        lang = _optval("--lang")
        out = _optval("--out") or os.path.join(OUT_DIR, "hf_gen.mp4")
        sf = _optval("--script-file")
        script = open(sf).read() if sf else _optval("--script", "")
        r = produce_from_script(out, script, brand, language=lang)
        print(f"RESULT={r or 'FAILED'}")
        sys.exit(0 if r else 2)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ids = list(PKGS) if (not args or args == ["all"]) else args
    print(f"producing {len(ids)} @ {QUALITY}")
    ok = 0
    for pid in ids:
        try:
            if produce(pid):
                ok += 1
        except Exception as e:
            import traceback
            print(f"!! {pid}: {e}\n{traceback.format_exc()[-800:]}")
    print(f"DONE {ok}/{len(ids)}")


if __name__ == "__main__":
    main()
