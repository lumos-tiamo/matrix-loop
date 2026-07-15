from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)

_SENTENCE_SPLIT = re.compile(r"[.!?。！？]+\s*|\n+")
_CJK = re.compile(r"[一-鿿぀-ヿ가-힯＀-￯]")
_CJK_BREAKERS = "，,、；;：:）)】」』"


def _is_cjk(s: str) -> bool:
    return _CJK.search(s) is not None


def _chunk_cjk(sentence: str, max_chars: int) -> list[str]:
    """Chunk a space-less CJK sentence into <= max_chars lines, breaking at punctuation/clause
    boundaries where possible (so lines don't end mid-phrase). Splits into clauses at secondary
    punctuation first, merges adjacent short clauses up to max_chars, and only hard-wraps a
    single clause that is itself longer than max_chars."""
    s = sentence.replace(" ", "").replace("　", "")
    # split AFTER each clause-ending punctuation, keeping the mark on its clause
    clauses = [c for c in (p.strip() for p in re.split(r"(?<=[，,、；;：:—…])", s)) if c]
    out: list[str] = []
    cur = ""
    for cl in clauses:
        if len(cl) > max_chars:                      # clause too long -> hard-wrap by chars
            if cur:
                out.append(cur.strip(_CJK_BREAKERS))
                cur = ""
            for i in range(0, len(cl), max_chars):
                piece = cl[i:i + max_chars].strip(_CJK_BREAKERS)
                if piece:
                    out.append(piece)
            continue
        if not cur:
            cur = cl
        elif len(cur) + len(cl) <= max_chars:        # merge short adjacent clauses onto one line
            cur += cl
        else:
            out.append(cur.strip(_CJK_BREAKERS))
            cur = cl
    if cur.strip(_CJK_BREAKERS):
        out.append(cur.strip(_CJK_BREAKERS))
    return [c for c in out if c]


def chunk_caption(text: str, *, max_words: int = 6, max_cjk_chars: int = 12) -> list[str]:
    """Split spoken text into short on-screen caption chunks. Breaks on sentence enders first;
    then CJK sentences (no spaces) chunk by character count, others by word count — so Chinese
    captions no longer collapse into one overflowing line."""
    text = (text or "").strip()
    if not text:
        return []
    chunks: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if _is_cjk(sentence):
            chunks.extend(_chunk_cjk(sentence, max_cjk_chars))
        else:
            words = sentence.split()
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
    # CJK-capable fonts FIRST: these also carry Latin glyphs, so they render the
    # Aurea 繁中 captions AND the English-account captions. Latin-only fonts (Arial/
    # DejaVu) drop to fallback — they turn CJK into ☐ tofu boxes (bug fixed 2026-07).
    for p in (
        # macOS CJK (cover zh-Hant/zh-Hans + Latin)
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        # Linux CJK (Noto) — for server/CI deploys
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        # Latin-only fallbacks (fine for English-only captions)
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    logger.warning("no truetype font found; captions fall back to the bitmap default "
                   "and will not size/wrap correctly — install a CJK-capable .ttf "
                   "(e.g. Noto Sans CJK / PingFang)")
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    if not text:
        return []
    # CJK has no spaces -> wrap character by character so lines never overflow the frame.
    if _is_cjk(text):
        lines: list[str] = []
        cur = ""
        for ch in text:
            if not cur or draw.textlength(cur + ch, font=font) <= max_width:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
        return lines
    words = text.split()
    lines = []
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


def render_caption_images(
    timings: list[tuple[str, float, float]],
    *,
    resolution: tuple[int, int] = (1080, 1920),
    out_dir: str = ".",
    font_size: int = 72,
) -> list[tuple[str, float, float]]:
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
