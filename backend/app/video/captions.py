from __future__ import annotations

import os
import re

_SENTENCE_SPLIT = re.compile(r"[.!?。！？]+\s*|\n+")


def chunk_caption(text: str, *, max_words: int = 6) -> list[str]:
    """Split spoken text into short on-screen caption chunks (<= max_words words each),
    breaking first on sentence enders then on word count."""
    text = (text or "").strip()
    if not text:
        return []
    chunks: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(text):
        words = sentence.split()
        if not words:
            continue
        for i in range(0, len(words), max_words):
            chunk = " ".join(words[i:i + max_words]).strip()
            if chunk:
                chunks.append(chunk)
    return chunks


def _fmt_ass_ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def plan_caption_timings(chunks: list[str], total_seconds: float) -> list[tuple[str, float, float]]:
    """Return [(text, start, end)] with each chunk's on-screen time proportional to its char length."""
    if not chunks or total_seconds <= 0:
        return []
    weights = [max(1, len(c)) for c in chunks]
    total_w = sum(weights)
    timings: list[tuple[str, float, float]] = []
    t = 0.0
    for chunk, wt in zip(chunks, weights):
        dur = total_seconds * (wt / total_w)
        timings.append((chunk.replace("\n", " "), t, t + dur))
        t += dur
    return timings


def build_ass(chunks: list[str], total_seconds: float, *, resolution: tuple[int, int] = (1080, 1920)) -> str:
    """Build an ASS subtitle document. Each chunk's on-screen time is proportional to its
    character length so it tracks the narration pace. Empty chunks -> header only."""
    w, h = resolution
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {w}",
        f"PlayResY: {h}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
        "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,72,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,"
        "4,1,2,60,60,180,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for text, start, end in plan_caption_timings(chunks, total_seconds):
        lines.append(
            f"Dialogue: 0,{_fmt_ass_ts(start)},{_fmt_ass_ts(end)},Default,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"


def _load_font(size: int):
    from PIL import ImageFont
    for p in (
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if not cur or draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_caption_images(timings, *, resolution=(1080, 1920), out_dir=".", font_size=72):
    """Render each caption to a full-frame transparent PNG (bottom-centred, outlined) via Pillow.
    Returns [(png_path, start, end)]. Portable: needs only ffmpeg's core `overlay` filter,
    no libass/drawtext."""
    from PIL import Image, ImageDraw

    w, h = resolution
    font = _load_font(font_size)
    out = []
    for i, (text, start, end) in enumerate(timings):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        lines = _wrap(draw, text, font, int(w * 0.9))
        line_h = font_size + 16
        y = int(h * 0.82) - line_h * len(lines)
        for ln in lines:
            tw = draw.textlength(ln, font=font)
            draw.text(((w - tw) / 2, y), ln, font=font, fill=(255, 255, 255, 255),
                      stroke_width=6, stroke_fill=(0, 0, 0, 255))
            y += line_h
        path = os.path.join(out_dir, f"cap_{i:03d}.png")
        img.save(path)
        out.append((path, start, end))
    return out
