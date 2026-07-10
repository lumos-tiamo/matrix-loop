from __future__ import annotations

import subprocess


def _default_run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout, p.stderr


def ffprobe_duration(path: str, run=None) -> float:
    """Return media duration in seconds via ffprobe. `run(cmd)->(rc,out,err)` is injectable for tests."""
    runner = run or _default_run
    rc, out, err = runner(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path]
    )
    if rc != 0:
        raise RuntimeError(f"ffprobe failed rc={rc}: {(err or out or '').strip()[:200]}")
    try:
        return float((out or "").strip())
    except ValueError as exc:
        raise RuntimeError(f"ffprobe returned non-numeric duration: {out!r}") from exc
