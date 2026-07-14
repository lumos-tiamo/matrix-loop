from __future__ import annotations

import os

import pytest

from app.image.fake import FakeImageProvider
from app.video.still import StillImageVisual
from app.video.tts.edge import EdgeTTSProvider


# ---------- edge TTS ----------

def test_edge_tts_synth_and_duration(tmp_path):
    def fake_synth(text, voice, out_path, rate, volume):
        assert voice == "zh-TW-HsiaoChenNeural"      # default zh-TW
        with open(out_path, "wb") as f:
            f.write(b"ID3fake-mp3-bytes")

    def fake_run(cmd):  # stand in for ffprobe
        return 0, "4.20", ""

    p = EdgeTTSProvider(output_dir=str(tmp_path), synth=fake_synth, run=fake_run)
    r = p.synthesize(text="大家好，我是 Aurea。")
    assert r.fmt == "mp3"
    assert r.duration_seconds == 4.2
    assert os.path.exists(r.audio_path) and r.audio_path.endswith(".mp3")


def test_edge_tts_voice_alias(tmp_path):
    captured = {}

    def fake_synth(text, voice, out_path, rate, volume):
        captured["voice"] = voice
        open(out_path, "wb").write(b"x")

    p = EdgeTTSProvider(output_dir=str(tmp_path), synth=fake_synth, run=lambda c: (0, "1.0", ""))
    p.synthesize(text="hi", voice="en-f")
    assert captured["voice"] == "en-US-AvaNeural"     # alias resolved


def test_edge_tts_empty_text_raises(tmp_path):
    p = EdgeTTSProvider(output_dir=str(tmp_path), synth=lambda *a: None)
    with pytest.raises(ValueError):
        p.synthesize(text="   ")


def test_edge_tts_no_audio_raises(tmp_path):
    def bad_synth(text, voice, out_path, rate, volume):
        pass  # writes nothing

    p = EdgeTTSProvider(output_dir=str(tmp_path), synth=bad_synth, run=lambda c: (0, "1", ""))
    with pytest.raises(RuntimeError, match="no audio"):
        p.synthesize(text="hi")


# ---------- StillImageVisual ----------

def test_still_visual_wraps_image_provider(tmp_path):
    img = FakeImageProvider(output_dir=str(tmp_path))
    vis = StillImageVisual(image_provider=img)
    r = vis.generate(script="Aurea talks airdrops", brief=None, params={})
    assert r.provider == "still"
    assert os.path.exists(r.metadata["path"])
    assert r.media_url == r.metadata["path"]


def test_still_visual_passes_refs_for_consistency(tmp_path):
    captured = {}

    class SpyImg:
        provider = "spy"
        name = "spy"

        def generate(self, *, prompt, refs=None, params=None):
            captured["refs"] = refs
            from app.image.base import ImageResult
            p = os.path.join(str(tmp_path), "a.png")
            open(p, "wb").write(b"x")
            return ImageResult(path=p, media_url=p, mime="image/png", provider="spy", prompt=prompt)

    vis = StillImageVisual(image_provider=SpyImg(), default_refs=["data:image/png;base64,BASE"])
    vis.generate(script="s", brief=None, params={})
    assert captured["refs"] == ["data:image/png;base64,BASE"]   # locks the Aurea look


# ---------- faceless still background (real ffmpeg) ----------

def _have(bin_):
    import shutil
    return shutil.which(bin_) is not None


@pytest.mark.skipif(not (_have("ffmpeg") and _have("ffprobe")), reason="ffmpeg/ffprobe required")
def test_faceless_still_bg_makes_fulllength_clip(tmp_path):
    from app.image.fake import FakeImageProvider
    from app.video.faceless import FacelessVideoProvider
    from app.video.ffmpeg_util import ffprobe_duration

    # a real (tiny) still to loop
    img = FakeImageProvider(output_dir=str(tmp_path)).generate(prompt="x")
    fv = FacelessVideoProvider(tts=None, visual=None, output_dir=str(tmp_path),
                               resolution=(360, 640))
    tmp = str(tmp_path)
    bg = fv._still_bg(img.path, duration=2.0, tmp=tmp)
    assert os.path.exists(bg)
    dur = ffprobe_duration(bg)
    assert 1.7 <= dur <= 2.4      # ~2s looped background


# ---------- avatar factory wiring ----------

def test_factory_avatar_resolves_faceless_still_edge(monkeypatch):
    from app.config import settings
    from app.video.factory import resolve_video_provider

    monkeypatch.setattr(settings, "video_provider", "avatar")
    monkeypatch.setattr(settings, "tts_provider", "edge")
    monkeypatch.setattr(settings, "image_provider", "fake")
    prov = resolve_video_provider()
    assert prov.name == "faceless"                       # composed provider
    assert prov._visual.name == "still"                  # still-image visual
    assert type(prov._tts).__name__ in ("EdgeTTSProvider", "FakeTTSProvider")
