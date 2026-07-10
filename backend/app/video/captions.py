from __future__ import annotations

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
    if chunks and total_seconds > 0:
        weights = [max(1, len(c)) for c in chunks]
        total_w = sum(weights)
        t = 0.0
        for chunk, wt in zip(chunks, weights):
            dur = total_seconds * (wt / total_w)
            start, end = t, t + dur
            t = end
            text = chunk.replace("\n", " ")
            lines.append(
                f"Dialogue: 0,{_fmt_ass_ts(start)},{_fmt_ass_ts(end)},Default,,0,0,0,,{text}"
            )
    return "\n".join(lines) + "\n"
