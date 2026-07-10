from __future__ import annotations

import pytest

from app.video.tts.openai import OpenAITTSProvider
from app.video.tts.say import SayTTSProvider


class _RunRecorder:
    """Fake run(cmd)->(rc,out,err). Returns a canned ffprobe duration for ffprobe calls."""
    def __init__(self, duration="2.50"):
        self.calls = []
        self._duration = duration

    def __call__(self, cmd):
        self.calls.append(cmd)
        if cmd and cmd[0] == "ffprobe":
            return 0, f"{self._duration}\n", ""
        return 0, "", ""


def test_say_builds_command_and_probes_duration(tmp_path):
    run = _RunRecorder(duration="3.00")
    p = SayTTSProvider(output_dir=str(tmp_path), run=run)
    res = p.synthesize(text="hello there friends")
    assert p.name == "say"
    assert res.fmt == "wav" and res.audio_path.endswith(".wav")
    assert res.duration_seconds == 3.0
    # say invoked with -f <textfile> -o <aiff>
    say_call = next(c for c in run.calls if c[0] == "say")
    assert "-f" in say_call and "-o" in say_call
    # ffmpeg aiff->wav invoked
    assert any(c[0] == "ffmpeg" for c in run.calls)


def test_say_raises_on_nonzero(tmp_path):
    def run(cmd):
        if cmd[0] == "say":
            return 1, "", "no voice"
        return 0, "", ""
    with pytest.raises(RuntimeError, match="say failed"):
        SayTTSProvider(output_dir=str(tmp_path), run=run).synthesize(text="x")


class _FakeResp:
    def __init__(self, content=b"ID3fakeaudio", status_code=200, text=""):
        self.content = content
        self.status_code = status_code
        self.text = text


def test_openai_posts_speech_and_writes_mp3(tmp_path):
    posts = []

    def http_post(url, headers, json):
        posts.append((url, headers, json))
        return _FakeResp()

    run = _RunRecorder(duration="4.20")
    p = OpenAITTSProvider(base_url="https://relay.example", api_key="sk-x",
                          model="tts-1", voice="alloy", output_dir=str(tmp_path),
                          http_post=http_post, run=run)
    res = p.synthesize(text="crypto markets moved")
    assert p.name == "openai"
    assert res.fmt == "mp3" and res.audio_path.endswith(".mp3")
    assert res.duration_seconds == 4.2
    url, headers, body = posts[0]
    assert url == "https://relay.example/v1/audio/speech"
    assert headers["Authorization"] == "Bearer sk-x"
    assert body["model"] == "tts-1" and body["voice"] == "alloy"
    assert body["input"] == "crypto markets moved" and body["response_format"] == "mp3"


def test_openai_raises_on_http_error(tmp_path):
    def http_post(url, headers, json):
        return _FakeResp(status_code=503, text="model_not_found")
    with pytest.raises(RuntimeError, match="HTTP 503"):
        OpenAITTSProvider(base_url="https://r", api_key="k", model="tts-1",
                          output_dir=str(tmp_path), http_post=http_post).synthesize(text="x")
