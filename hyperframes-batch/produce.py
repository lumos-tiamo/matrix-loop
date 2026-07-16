#!/usr/bin/env python3
"""Phase B producer: content package -> publish-ready MP4 with narration.
Borrows the ai-dictionary approach: free Edge-TTS voiceover, audio-timed scenes.
Pipeline per id: synth voice (edge-tts) -> measure -> audio-timed scene spans ->
generate HyperFrames HTML -> render (silent) -> mux voice -> backend/data/videos/hf_<id>.mp4

Usage:
  backend/.venv/bin/python produce.py QY-1 AU-4            # specific
  backend/.venv/bin/python produce.py all --quality draft  # whole batch
"""
import asyncio, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen_hyperframes import build, BRAND  # noqa: E402

PKGS = {p["id"]: p for p in json.load(open("/Users/aa00102/matrix-loop/_content_packages_2026-07-16.json"))["packages"]}
OUT_DIR = "/Users/aa00102/matrix-loop/backend/data/videos"
COMP_DIR = os.path.join(HERE, "compositions")
MAT_DIR = os.path.join(HERE, "material")
os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(COMP_DIR, exist_ok=True); os.makedirs(MAT_DIR, exist_ok=True)

VOICE = {  # per-account edge-tts voice
    "AE": "en-US-GuyNeural", "CC": "en-US-EricNeural",
    "QY": "en-US-AriaNeural", "AU": "zh-TW-HsiaoChenNeural",
}
PAUSE = 0.45   # seconds of breathing room added per scene
QUALITY = "draft"


def ffprobe_dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nk=1:nw=1", path], capture_output=True, text=True)
    return float(out.stdout.strip() or 0)


async def synth(text, voice, mp3_path):
    import edge_tts
    comm = edge_tts.Communicate(text, voice)
    with open(mp3_path, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])


def produce(pid):
    pkg = PKGS[pid]
    pre = pid.split("-")[0]
    voice = VOICE[pre]
    scenes = pkg.get("scenes") or []
    narrs = [(s.get("narration") or "").strip() or "…" for s in scenes]

    # 1) synth per-scene audio -> exact per-scene spoken durations (accurate alignment)
    segs, durs = [], []
    for i, nar in enumerate(narrs):
        seg = os.path.join(MAT_DIR, f"{pid}.seg{i}.mp3")
        asyncio.run(synth(nar, voice, seg))
        d = ffprobe_dur(seg)
        segs.append(seg); durs.append(max(1.2, d))

    # 2) audio-timed spans (start cumulative, dur = spoken + PAUSE)
    spans, cursor = [], 0.0
    for d in durs:
        spans.append((round(cursor, 2), round(d + PAUSE, 2)))
        cursor = round(cursor + d + PAUSE, 2)

    # 3) build a concatenated voice track matching the spans (seg + PAUSE silence each)
    voice_mp3 = os.path.join(MAT_DIR, f"{pid}.voice.mp3")
    sil = os.path.join(MAT_DIR, "_sil.mp3")
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono",
                    "-t", str(PAUSE), "-c:a", "libmp3lame", sil], capture_output=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as lf:
        for seg in segs:
            lf.write(f"file '{seg}'\nfile '{sil}'\n")
        listfile = lf.name
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                    "-c:a", "libmp3lame", "-ar", "24000", voice_mp3], capture_output=True)

    # 4) generate HTML with audio-timed spans
    doc, total = build(pkg, spans=spans)
    comp = os.path.join(COMP_DIR, f"{pid}.html")
    open(comp, "w").write(doc)

    # 5) render silent
    silent = os.path.join(tempfile.gettempdir(), f"hf_{pid}.silent.mp4")
    env = dict(os.environ, HYPERFRAMES_SKIP_SKILLS="1")
    r = subprocess.run(["npx", "hyperframes", "render", ".", "-c", f"compositions/{pid}.html",
                        "-o", silent, "-q", QUALITY], cwd=HERE, env=env,
                       capture_output=True, text=True)
    if not os.path.exists(silent):
        print(f"!! render failed for {pid}:\n{r.stdout[-800:]}\n{r.stderr[-400:]}")
        return None

    # 6) mux voice
    out = os.path.join(OUT_DIR, f"hf_{pid}.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", voice_mp3,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", out],
                   capture_output=True)
    vdur = ffprobe_dur(out)
    # cleanup segs
    for seg in segs:
        try: os.remove(seg)
        except OSError: pass
    print(f"✓ {pid}: {len(scenes)} scenes · {vdur:.1f}s · voice={voice} -> {out}")
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    global QUALITY
    for a in sys.argv[1:]:
        if a.startswith("--quality"):
            QUALITY = a.split("=")[-1] if "=" in a else "draft"
    ids = list(PKGS) if (not args or args == ["all"]) else args
    print(f"producing {len(ids)} video(s) @ quality={QUALITY}")
    ok = 0
    for pid in ids:
        try:
            if produce(pid): ok += 1
        except Exception as e:
            print(f"!! {pid} error: {e}")
    print(f"DONE: {ok}/{len(ids)} produced -> {OUT_DIR}")


if __name__ == "__main__":
    main()
