"""TDD: SeedanceVideoProvider — injected fake run, hermetic (no real CLI calls)."""
from __future__ import annotations

import json
import os

import pytest

from app.video.seedance import SeedanceVideoProvider


def _make_run(*responses):
    """Return a fake _run callable that yields successive (rc, stdout, stderr) tuples."""
    calls = list(responses)
    idx = [0]

    def _run(args):
        i = idx[0]
        idx[0] += 1
        return calls[i]

    return _run


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_happy_path_returns_video_result(tmp_path):
    submit_resp = json.dumps({"submit_id": "s1", "gen_status": "querying"})
    query_resp = json.dumps(
        {
            "gen_status": "success",
            "download_path": "/x/out/clip_s1.mp4",
            "duration": 5,
            "credit_cost": 8,
        }
    )
    provider = SeedanceVideoProvider(
        output_dir=str(tmp_path),
        public_base_url="http://127.0.0.1:8010",
        run=_make_run((0, submit_resp, ""), (0, query_resp, "")),
        sleep=lambda s: None,
    )
    result = provider.generate(script="buy gold now", brief=None, params={})
    assert result.media_url.endswith("/media/clip_s1.mp4")
    assert result.provider == "seedance"
    assert result.dedup_key == "s1"
    assert result.cost == 8.0
    assert result.duration == 5.0
    assert result.metadata["submit_id"] == "s1"


# ---------------------------------------------------------------------------
# Permission / plain-text error (non-JSON stdout)
# ---------------------------------------------------------------------------

def test_permission_error_raises_runtime_error():
    plain_error = "当前账号没有 dreamina_cli 使用权限: account not in allowlist"
    provider = SeedanceVideoProvider(
        run=_make_run((0, plain_error, "")),
        sleep=lambda s: None,
    )
    with pytest.raises(RuntimeError, match="seedance submit failed"):
        provider.generate(script="anything", brief=None, params={})


# ---------------------------------------------------------------------------
# fail status on query_result
# ---------------------------------------------------------------------------

def test_query_fail_status_raises_runtime_error():
    submit_resp = json.dumps({"submit_id": "s2", "gen_status": "querying"})
    query_resp = json.dumps({"gen_status": "fail", "fail_reason": "nsfw"})
    provider = SeedanceVideoProvider(
        run=_make_run((0, submit_resp, ""), (0, query_resp, "")),
        sleep=lambda s: None,
    )
    with pytest.raises(RuntimeError, match="nsfw"):
        provider.generate(script="bad content", brief=None, params={})


# ---------------------------------------------------------------------------
# fail status on submit
# ---------------------------------------------------------------------------

def test_submit_fail_status_raises_runtime_error():
    submit_resp = json.dumps({"submit_id": None, "gen_status": "fail", "fail_reason": "quota exceeded"})
    provider = SeedanceVideoProvider(
        run=_make_run((0, submit_resp, "")),
        sleep=lambda s: None,
    )
    with pytest.raises(RuntimeError, match="seedance submit rejected"):
        provider.generate(script="anything", brief=None, params={})


# ---------------------------------------------------------------------------
# Fallback filename: no path key in result → newest .mp4 in output_dir
# ---------------------------------------------------------------------------

def test_fallback_filename_from_newest_mp4(tmp_path):
    # Drop a dummy mp4 in the output dir
    dummy = tmp_path / "clip_fallback.mp4"
    dummy.write_bytes(b"\x00")

    submit_resp = json.dumps({"submit_id": "s3", "gen_status": "querying"})
    # Success but NO path/download_path/etc. key
    query_resp = json.dumps({"gen_status": "success", "duration": 5, "credit_cost": 2})

    provider = SeedanceVideoProvider(
        output_dir=str(tmp_path),
        public_base_url="http://127.0.0.1:8010",
        run=_make_run((0, submit_resp, ""), (0, query_resp, "")),
        sleep=lambda s: None,
    )
    result = provider.generate(script="test fallback", brief=None, params={})
    assert result.media_url.endswith("/media/clip_fallback.mp4")


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------

def test_poll_timeout_raises_runtime_error():
    submit_resp = json.dumps({"submit_id": "s4", "gen_status": "querying"})
    # Always return "querying" so we time out
    query_resp = json.dumps({"gen_status": "querying"})

    # Use poll_attempts=3 to keep the test fast
    provider = SeedanceVideoProvider(
        run=_make_run(
            (0, submit_resp, ""),
            (0, query_resp, ""),
            (0, query_resp, ""),
            (0, query_resp, ""),
        ),
        sleep=lambda s: None,
        poll_attempts=3,
    )
    with pytest.raises(RuntimeError, match="timed out"):
        provider.generate(script="long running", brief=None, params={})


# ---------------------------------------------------------------------------
# Custom visual_prompt via params
# ---------------------------------------------------------------------------

def test_custom_visual_prompt_passed_through(tmp_path):
    submit_resp = json.dumps({"submit_id": "s5", "gen_status": "querying"})
    query_resp = json.dumps(
        {"gen_status": "success", "download_path": "/x/out/clip.mp4", "duration": 5, "credit_cost": 1}
    )

    captured = {}

    def _run(args):
        # Capture the text2video call args
        if args[0] == "text2video":
            captured["args"] = args
            return 0, submit_resp, ""
        return 0, query_resp, ""

    provider = SeedanceVideoProvider(
        output_dir=str(tmp_path),
        run=_run,
        sleep=lambda s: None,
    )
    provider.generate(script="ignored", brief=None, params={"visual_prompt": "neon city rain"})
    assert any("neon city rain" in a for a in captured["args"])
