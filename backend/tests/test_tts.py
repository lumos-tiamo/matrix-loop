from __future__ import annotations

import wave

from app.video.tts.base import TTSResult
from app.video.tts.fake import FakeTTSProvider


def test_fake_tts_duration_from_word_count(tmp_path):
    p = FakeTTSProvider(output_dir=str(tmp_path))
    # 27 words -> 27/2.7 = 10.0s
    text = " ".join(["word"] * 27)
    res = p.synthesize(text=text)
    assert isinstance(res, TTSResult)
    assert res.fmt == "wav"
    assert abs(res.duration_seconds - 10.0) < 0.01
    assert p.name == "fake"


def test_fake_tts_writes_playable_silence_wav(tmp_path):
    p = FakeTTSProvider(output_dir=str(tmp_path), rate=16000)
    res = p.synthesize(text="hello world here")   # 3 words -> max(1.0, 1.11) = 1.11s
    with wave.open(res.audio_path, "rb") as w:
        assert w.getnchannels() == 1
        assert w.getframerate() == 16000
        frames = w.getnframes()
    assert abs(frames / 16000 - res.duration_seconds) < 0.05


def test_fake_tts_empty_text_min_duration(tmp_path):
    p = FakeTTSProvider(output_dir=str(tmp_path))
    res = p.synthesize(text="")
    assert res.duration_seconds == 1.0
