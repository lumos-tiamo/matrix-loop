from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from app.video.faceless import FacelessVideoProvider
from app.video.fake import FakeVideoProvider
from app.video.tts.fake import FakeTTSProvider

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _stream_types(path):
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True,
    )
    return p.stdout


def _duration(path):
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True,
    )
    return float(p.stdout.strip())


def test_narration_strips_heading_lines(tmp_path):
    prov = FacelessVideoProvider(tts=FakeTTSProvider(output_dir=str(tmp_path)),
                                 visual=FakeVideoProvider(), output_dir=str(tmp_path))
    assert prov._narration("# Title\n\nHook line.\nSecond line.") == "Hook line. Second line."


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe required for real compose")
def test_faceless_composes_real_playable_mp4(tmp_path):
    tts = FakeTTSProvider(output_dir=str(tmp_path))
    prov = FacelessVideoProvider(
        tts=tts, visual=FakeVideoProvider(),
        output_dir=str(tmp_path), public_base_url="http://127.0.0.1:8010",
    )
    script = "Bitcoin broke out today. Here is why it matters. Watch the liquidity move."
    res = prov.generate(script=script, brief=None, params={})

    assert res.provider == "faceless"
    assert res.metadata["visual_provider"] == "fake"
    assert res.metadata["caption_chunks"] >= 3
    fname = res.media_url.rsplit("/", 1)[-1]
    path = os.path.join(str(tmp_path), fname)
    assert os.path.exists(path)
    streams = _stream_types(path)
    assert "video" in streams and "audio" in streams
    # duration tracks the TTS voiceover length (11 words / 2.7 ~= 4.07s)
    assert abs(_duration(path) - res.duration) < 1.0
