from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time

from app.video.base import VideoResult
from app.video.ffmpeg_util import ffprobe_duration

logger = logging.getLogger(__name__)

# waoowaoo task status strings (src/lib/task/types.ts TASK_STATUS)
_TERMINAL = {"completed", "failed", "canceled", "dismissed"}
_SUCCESS = "completed"


class WaoowaooBrollProvider:
    """A *visual* (clip-like) provider that drives the waoowaoo AI-film pipeline
    (story -> script -> storyboard -> panel images -> per-panel Kling clips) over its
    internal HTTP API, then ffmpeg-concats the panel clips into a single vertical b-roll.
    FacelessVideoProvider consumes it as the background track and lays the TTS narration +
    captions on top (its ``else`` background branch already loops/trims/crops a video bg).

    Auth uses waoowaoo's INTERNAL_TASK_TOKEN + a pre-provisioned service user
    (x-internal-task-token / x-internal-user-id); the AI-model API keys live inside
    waoowaoo, never here. http_*/sleep/run are injectable so tests never hit the network
    or a real ffmpeg (repo convention, see CanvasImageProvider).

    On any failure it degrades to ``fallback_visual`` (e.g. a StillImageVisual) when one is
    provided, so a waoowaoo outage never stalls the loop — the account still gets a narrated
    video, just with a still background instead of drama clips. Returns a VideoResult-shaped
    object with ``provider="waoowaoo"`` and ``media_url`` = the local b-roll path.
    """

    name = "waoowaoo"

    def __init__(
        self,
        *,
        base_url: str,
        internal_token: str,
        user_id: str,
        sf_api_key: str = "",
        sf_base_url: str = "https://api.siliconflow.cn/v1",
        sf_video_model: str = "Wan-AI/Wan2.2-I2V-A14B",
        sf_max_attempts: int = 3,
        output_dir: str = "./data/videos",
        public_base_url: str = "http://127.0.0.1:8010",
        panels: int = 6,
        locale: str = "en",
        resolution: tuple[int, int] = (1080, 1920),
        story_writer=None,          # optional callable(script, brief) -> str
        fallback_visual=None,
        http_post=None,
        http_get=None,
        run=None,
        poll_interval: float = 3.0,
        max_wait: float = 600.0,
        proc_timeout: int = 600,
        sleep=time.sleep,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.internal_token = internal_token or ""
        self.user_id = user_id or ""
        # Video is generated via SiliconFlow directly (waoowaoo's openai-compat template
        # can't express SiliconFlow's POST-body status polling), so the adapter owns i2v.
        self.sf_api_key = sf_api_key or ""
        self.sf_base_url = (sf_base_url or "").rstrip("/")
        self.sf_video_model = sf_video_model or "Wan-AI/Wan2.2-I2V-A14B"
        self._sf_max_attempts = max(1, int(sf_max_attempts or 1))
        self.output_dir = os.path.abspath(output_dir)
        self.public_base_url = (public_base_url or "").rstrip("/")
        self.panels = max(1, int(panels or 6))
        self.locale = locale or "en"
        self._w, self._h = resolution
        self._story_writer = story_writer
        self._fallback = fallback_visual
        self._http_post = http_post or self._default_post
        self._http_get = http_get or self._default_get
        self._run = run or self._default_run
        self.poll_interval = poll_interval
        self.max_wait = max_wait
        self._proc_timeout = proc_timeout
        self._sleep = sleep

    # ---- injectable IO defaults -------------------------------------------------
    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.internal_token:
            h["x-internal-task-token"] = self.internal_token
        if self.user_id:
            h["x-internal-user-id"] = self.user_id
        h["Accept-Language"] = "en-US" if self.locale.startswith("en") else self.locale
        return h

    def _default_post(self, url: str, headers: dict, json: dict) -> dict:
        import httpx

        resp = httpx.post(url, headers=headers, json=json, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def _default_get(self, url: str, headers: dict) -> dict:
        import httpx

        resp = httpx.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def _default_run(self, cmd):
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=self._proc_timeout)
        return p.returncode, p.stdout, p.stderr

    # ---- public entrypoint ------------------------------------------------------
    def generate(self, *, script: str, brief, params: dict) -> VideoResult:
        params = params or {}
        try:
            return self._generate_broll(script, brief, params)
        except Exception as exc:  # noqa: BLE001 - degrade, don't stall the loop
            logger.warning("waoowaoo b-roll failed (%s: %s)", exc.__class__.__name__, exc)
            if self._fallback is not None:
                logger.warning("waoowaoo: falling back to '%s' visual",
                               getattr(self._fallback, "name", "?"))
                return self._fallback.generate(script=script, brief=brief, params=params)
            raise

    # ---- pipeline ---------------------------------------------------------------
    def _generate_broll(self, script: str, brief, params: dict) -> VideoResult:
        if not (self.base_url and self.internal_token and self.user_id):
            raise RuntimeError("waoowaoo: base_url/internal_token/user_id not configured")
        if not self.sf_api_key:
            raise RuntimeError("waoowaoo: sf_api_key not configured (SiliconFlow i2v)")

        story = self._build_story(script, brief)
        project_id = self._create_project(brief)
        episode_id = self._create_episode(project_id, story)
        logger.info("waoowaoo: project=%s episode=%s", project_id, episode_id)

        self._run_task(project_id, "story-to-script-stream",
                       {"episodeId": episode_id, "content": story, "locale": self.locale})
        self._run_task(project_id, "script-to-storyboard-stream",
                       {"episodeId": episode_id, "locale": self.locale})

        panel_ids = self._panel_ids(project_id, episode_id)[: self.panels]
        if not panel_ids:
            raise RuntimeError(f"waoowaoo: storyboard produced no panels (episode {episode_id})")
        self._generate_panel_images(project_id, episode_id, panel_ids)

        clip_urls = self._panel_clip_urls(project_id, episode_id, panel_ids)
        if not clip_urls:
            raise RuntimeError(f"waoowaoo: no panel clips for episode {episode_id}")
        broll_path, duration = self._concat_clips(clip_urls, episode_id)

        return VideoResult(
            media_url=broll_path,        # local abs path; faceless uses it as the video bg
            duration=duration,
            cost=0.0,                    # billed inside waoowaoo (BILLING_MODE=OFF for OSS)
            provider=self.name,
            dedup_key=f"waoowaoo:{episode_id}",
            metadata={"episode_id": episode_id, "project_id": project_id,
                      "panel_count": len(clip_urls), "path": broll_path},
        )

    def _build_story(self, script: str, brief) -> str:
        """Turn the spoken narration into narrative/scene text waoowaoo can dramatize.
        Falls back to the raw script when no story_writer is wired or it errors."""
        if self._story_writer is None:
            return script
        try:
            story = (self._story_writer(script, brief) or "").strip()
            return story or script
        except Exception as exc:  # noqa: BLE001
            logger.warning("waoowaoo: story_writer failed (%s); using raw script", exc)
            return script

    # ---- HTTP steps -------------------------------------------------------------
    def _post(self, path: str, body: dict) -> dict:
        return self._http_post(f"{self.base_url}{path}", self._headers(), body)

    def _get(self, path: str) -> dict:
        return self._http_get(f"{self.base_url}{path}", self._headers())

    def _create_project(self, brief) -> str:
        name = f"matrixloop {getattr(brief, 'main_direction', '') or 'video'}".strip()[:60]
        data = self._post("/api/projects", {"name": name})
        pid = ((data.get("project") or {}).get("id")) or data.get("id")
        if not pid:
            raise RuntimeError(f"waoowaoo: create project returned no id: {str(data)[:200]}")
        return pid

    def _create_episode(self, project_id: str, story: str) -> str:
        data = self._post(
            f"/api/novel-promotion/{project_id}/episodes",
            {"name": "Episode 1", "novelText": story},
        )
        eid = ((data.get("episode") or {}).get("id")) or data.get("id")
        if not eid:
            raise RuntimeError(f"waoowaoo: create episode returned no id: {str(data)[:200]}")
        return eid

    def _run_task(self, project_id: str, endpoint: str, body: dict) -> None:
        data = self._post(f"/api/novel-promotion/{project_id}/{endpoint}", body)
        task_id = data.get("taskId") or data.get("id")
        if not task_id:
            raise RuntimeError(f"waoowaoo: {endpoint} returned no taskId: {str(data)[:200]}")
        self._poll_task(task_id, label=endpoint)

    def _poll_task(self, task_id: str, *, label: str = "task") -> None:
        waited = 0.0
        while True:
            rec = self._get(f"/api/tasks/{task_id}")
            task = rec.get("task") or rec
            status = (task.get("status") or "").lower()
            if status in _TERMINAL:
                if status != _SUCCESS:
                    msg = task.get("errorMessage") or task.get("errorCode") or status
                    raise RuntimeError(f"waoowaoo {label} task {task_id} {status}: {msg}")
                return
            if waited >= self.max_wait:
                raise TimeoutError(f"waoowaoo {label} task {task_id} not done after {self.max_wait}s")
            self._sleep(self.poll_interval)
            waited += self.poll_interval

    def _episode(self, project_id: str, episode_id: str) -> dict:
        data = self._get(f"/api/novel-promotion/{project_id}/episodes/{episode_id}")
        return data.get("episode") or data

    def _panels(self, project_id: str, episode_id: str) -> list[dict]:
        ep = self._episode(project_id, episode_id)
        panels: list[dict] = []
        for sb in ep.get("storyboards") or []:
            panels.extend(sb.get("panels") or [])
        panels.sort(key=lambda p: (p.get("panelIndex") if p.get("panelIndex") is not None else 0))
        return panels

    def _panel_ids(self, project_id: str, episode_id: str) -> list[str]:
        return [p["id"] for p in self._panels(project_id, episode_id) if p.get("id")]

    def _generate_panel_images(self, project_id: str, episode_id: str, panel_ids: list[str]) -> None:
        for pid in panel_ids:
            self._post(f"/api/novel-promotion/{project_id}/regenerate-panel-image",
                       {"panelId": pid, "count": 1})
        # First-generation auto-selects candidate[0] as imageUrl; poll resource state so we
        # don't depend on per-task ids for the batch.
        self._poll_until(
            lambda: self._panels_ready(project_id, episode_id, panel_ids, "imageUrl"),
            label="panel images",
        )

    def _panel_clip_urls(self, project_id: str, episode_id: str, panel_ids: list[str]) -> list[str]:
        """Generate one i2v clip per panel via SiliconFlow, in panel order.
        Each panel's waoowaoo image is base64'd (SiliconFlow rejects fetch-by-URL) and its
        storyboard video_prompt drives the motion. Returns downloadable SiliconFlow clip URLs."""
        wanted = set(panel_ids)
        panels = [p for p in self._panels(project_id, episode_id)
                  if p.get("id") in wanted and p.get("imageUrl")]
        urls: list[str] = []
        for p in panels:
            image = self._fetch_image_datauri(str(p["imageUrl"]))
            prompt = (p.get("videoPrompt") or p.get("video_prompt") or p.get("description")
                      or "subtle cinematic motion, the scene gently comes alive")
            urls.append(self._siliconflow_i2v(image, str(prompt)[:800]))
        return urls

    def _fetch_image_datauri(self, image_url: str) -> str:
        import base64
        import httpx

        url = image_url if image_url.startswith("http") else f"{self.base_url}{image_url}"
        headers = self._headers() if url.startswith(self.base_url) else {}
        resp = httpx.get(url, headers=headers, timeout=120)
        resp.raise_for_status()
        content = resp.content
        # waoowaoo can mislabel Content-Type (serves PNG bytes as image/jpeg), which makes the
        # downstream i2v decoder reject the frame — sniff the real type from magic bytes.
        mime = self._sniff_image_mime(content) or (resp.headers.get("content-type") or "image/png").split(";")[0]
        return f"data:{mime};base64,{base64.b64encode(content).decode()}"

    @staticmethod
    def _sniff_image_mime(b: bytes) -> str | None:
        if b[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if b[:3] == b"\xff\xd8\xff":
            return "image/jpeg"
        if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
            return "image/webp"
        return None

    def _siliconflow_i2v(self, image_datauri: str, prompt: str) -> str:
        """Generate one i2v clip, retrying transient failures. Wan2.2-I2V fails intermittently
        with an empty reason (SiliconFlow-side capacity), so retry a few times before giving up.
        image must be a base64 data URI; image_size is omitted (inferred) — both required."""
        last: Exception | None = None
        for attempt in range(self._sf_max_attempts):
            try:
                return self._sf_i2v_once(image_datauri, prompt)
            except (RuntimeError,) as exc:
                last = exc
                logger.warning("siliconflow i2v attempt %d/%d failed: %s",
                               attempt + 1, self._sf_max_attempts, exc)
                self._sleep(min(60.0, 10.0 * (attempt + 1)))  # backoff; SF drops jobs under load
        raise RuntimeError(f"siliconflow i2v failed after {self._sf_max_attempts} attempts: {last}")

    def _sf_i2v_once(self, image_datauri: str, prompt: str) -> str:
        import httpx

        h = {"Authorization": f"Bearer {self.sf_api_key}", "Content-Type": "application/json"}
        sub = httpx.post(f"{self.sf_base_url}/video/submit", headers=h, timeout=120,
                         json={"model": self.sf_video_model, "prompt": prompt, "image": image_datauri})
        sub.raise_for_status()
        rid = sub.json().get("requestId") or sub.json().get("request_id")
        if not rid:
            raise RuntimeError(f"siliconflow submit returned no requestId: {sub.text[:200]}")
        waited = 0.0
        while True:
            st = httpx.post(f"{self.sf_base_url}/video/status", headers=h, timeout=120,
                            json={"requestId": rid})
            st.raise_for_status()
            data = st.json()
            status = str(data.get("status") or "")
            if status in ("Succeed", "Success"):
                videos = (data.get("results") or {}).get("videos") or []
                url = videos[0].get("url") if videos and isinstance(videos[0], dict) else None
                if not url:
                    raise RuntimeError(f"siliconflow video {rid} succeeded but no url: {str(data)[:200]}")
                return url
            if status in ("Failed", "Error"):
                raise RuntimeError(f"siliconflow video {rid} failed: {data.get('reason') or status}")
            if waited >= self.max_wait:
                raise TimeoutError(f"siliconflow video {rid} not done after {self.max_wait}s")
            self._sleep(self.poll_interval)
            waited += self.poll_interval

    def _panels_ready(self, project_id: str, episode_id: str, panel_ids: list[str], field: str) -> bool:
        wanted = set(panel_ids)
        ready = [p for p in self._panels(project_id, episode_id)
                 if p.get("id") in wanted and p.get(field)]
        return len(ready) >= len(wanted)

    def _poll_until(self, predicate, *, label: str) -> None:
        waited = 0.0
        while True:
            if predicate():
                return
            if waited >= self.max_wait:
                raise TimeoutError(f"waoowaoo {label} not ready after {self.max_wait}s")
            self._sleep(self.poll_interval)
            waited += self.poll_interval

    # ---- ffmpeg -----------------------------------------------------------------
    def _download(self, url: str, dest: str) -> str:
        import httpx

        # SiliconFlow clip URLs are public object storage; only waoowaoo-hosted URLs need auth.
        headers = self._headers() if url.startswith(self.base_url) else {}
        with httpx.stream("GET", url, headers=headers, timeout=120) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in resp.iter_bytes():
                    fh.write(chunk)
        return dest

    def _normalize(self, src: str, dest: str) -> None:
        """Re-encode a clip to the target 9:16 canvas (drop audio) so the concat demuxer
        can stream-copy heterogeneous Kling outputs into one file."""
        vf = (f"scale={self._w}:{self._h}:force_original_aspect_ratio=increase,"
              f"crop={self._w}:{self._h},setsar=1")
        rc, o, e = self._run([
            "ffmpeg", "-y", "-i", src, "-an", "-vf", vf, "-r", "30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", dest,
        ])
        if rc != 0:
            raise RuntimeError(f"waoowaoo normalize failed rc={rc}: {(e or o or '').strip()[:200]}")

    def _concat_clips(self, clip_urls: list[str], episode_id: str) -> tuple[str, float]:
        os.makedirs(self.output_dir, exist_ok=True)
        tmp = tempfile.mkdtemp(prefix="waoowaoo_")
        try:
            norm_paths: list[str] = []
            for i, url in enumerate(clip_urls):
                raw = self._download(url, os.path.join(tmp, f"clip_{i:03d}.src.mp4"))
                norm = os.path.join(tmp, f"clip_{i:03d}.mp4")
                self._normalize(raw, norm)
                norm_paths.append(norm)

            list_file = os.path.join(tmp, "concat.txt")
            with open(list_file, "w") as fh:
                for p in norm_paths:
                    fh.write(f"file '{p}'\n")

            fname = f"waoowaoo_{episode_id}.mp4"
            out_path = os.path.join(self.output_dir, fname)
            rc, o, e = self._run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
                "-c", "copy", out_path,
            ])
            if rc != 0:
                raise RuntimeError(f"waoowaoo concat failed rc={rc}: {(e or o or '').strip()[:200]}")
            duration = ffprobe_duration(out_path, run=self._run)
            return out_path, round(duration, 2)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
