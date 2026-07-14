"""SQLite 作业存储 —— 重启不丢、原子领取、崩溃恢复。

同步实现 + 线程锁；异步调用方用 asyncio.to_thread 包一层，避免阻塞事件循环。
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import List, Optional, Tuple

from .models import Artifact, JobRecord, JobSpec, JobStatus, JobType

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id      TEXT PRIMARY KEY,
    batch_id    TEXT NOT NULL,
    client_ref  TEXT,
    type        TEXT NOT NULL,
    provider    TEXT NOT NULL,
    prompt      TEXT NOT NULL,
    input_image TEXT,
    params      TEXT NOT NULL DEFAULT '{}',
    status      TEXT NOT NULL,
    progress    REAL NOT NULL DEFAULT 0,
    artifacts   TEXT NOT NULL DEFAULT '[]',
    error       TEXT,
    attempts    INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_batch ON jobs(batch_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
"""


def _now() -> float:
    return time.time()


class JobStore:
    def __init__(self, db_path: str, clock=_now):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._clock = clock
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---- 写入 ----

    def create_batch(self, batch_id: str, specs_with_ids: List[Tuple[str, JobSpec, str]]) -> List[str]:
        """specs_with_ids: [(job_id, spec, resolved_provider), ...]，返回 job_id 列表。"""
        now = self._clock()
        rows = []
        for job_id, spec, provider in specs_with_ids:
            rows.append(
                (
                    job_id,
                    batch_id,
                    spec.client_ref,
                    spec.type.value,
                    provider,
                    spec.prompt,
                    spec.input_image,
                    json.dumps(spec.params, ensure_ascii=False),
                    JobStatus.QUEUED.value,
                    0.0,
                    "[]",
                    None,
                    0,
                    now,
                    now,
                )
            )
        with self._lock:
            self._conn.executemany(
                """INSERT INTO jobs
                   (job_id, batch_id, client_ref, type, provider, prompt, input_image,
                    params, status, progress, artifacts, error, attempts, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            self._conn.commit()
        return [r[0] for r in rows]

    def claim_next(self) -> Optional[dict]:
        """原子领取一个 queued 作业并置为 running，返回执行所需字段（含 spec）。"""
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM jobs WHERE status=? ORDER BY created_at ASC LIMIT 1",
                (JobStatus.QUEUED.value,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            now = self._clock()
            upd = self._conn.execute(
                "UPDATE jobs SET status=?, updated_at=?, attempts=attempts+1 "
                "WHERE job_id=? AND status=?",
                (JobStatus.RUNNING.value, now, row["job_id"], JobStatus.QUEUED.value),
            )
            self._conn.commit()
            if upd.rowcount != 1:
                return None  # 被别的 worker 抢走
            return {
                "job_id": row["job_id"],
                "spec": self._row_to_spec(row),
                "provider": row["provider"],
                "attempts": row["attempts"] + 1,
            }

    def set_progress(self, job_id: str, progress: float) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET progress=?, updated_at=? WHERE job_id=?",
                (max(0.0, min(1.0, progress)), self._clock(), job_id),
            )
            self._conn.commit()

    def set_succeeded(self, job_id: str, artifacts: List[Artifact]) -> None:
        payload = json.dumps([a.model_dump() for a in artifacts], ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status=?, progress=1.0, artifacts=?, error=NULL, updated_at=? "
                "WHERE job_id=?",
                (JobStatus.SUCCEEDED.value, payload, self._clock(), job_id),
            )
            self._conn.commit()

    def set_failed(self, job_id: str, error: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status=?, error=?, updated_at=? WHERE job_id=?",
                (JobStatus.FAILED.value, error[:2000], self._clock(), job_id),
            )
            self._conn.commit()

    def requeue(self, job_id: str, error: str = "") -> None:
        """重试：置回 queued，供 worker 再次领取。"""
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status=?, error=?, updated_at=? WHERE job_id=?",
                (JobStatus.QUEUED.value, error[:2000] or None, self._clock(), job_id),
            )
            self._conn.commit()

    def cancel(self, job_id: str) -> bool:
        """只允许取消尚未进入终态的作业。"""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE jobs SET status=?, updated_at=? WHERE job_id=? AND status IN (?,?)",
                (
                    JobStatus.CANCELED.value,
                    self._clock(),
                    job_id,
                    JobStatus.QUEUED.value,
                    JobStatus.RUNNING.value,
                ),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def recover_stuck(self) -> int:
        """启动时把卡在 running 的作业重新入队（崩溃恢复）。返回恢复数量。"""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE jobs SET status=?, updated_at=? WHERE status=?",
                (JobStatus.QUEUED.value, self._clock(), JobStatus.RUNNING.value),
            )
            self._conn.commit()
            return cur.rowcount

    # ---- 读取 ----

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def list(
        self, status: Optional[str] = None, batch_id: Optional[str] = None, limit: int = 200
    ) -> List[JobRecord]:
        clauses, args = [], []
        if status:
            clauses.append("status=?")
            args.append(status)
        if batch_id:
            clauses.append("batch_id=?")
            args.append(batch_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        args.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ?", args
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def count_active(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS c FROM jobs WHERE status IN (?,?)",
                (JobStatus.QUEUED.value, JobStatus.RUNNING.value),
            ).fetchone()
        return int(row["c"])

    # ---- 行转换 ----

    @staticmethod
    def _row_to_spec(row: sqlite3.Row) -> JobSpec:
        return JobSpec.model_construct(
            type=JobType(row["type"]),
            prompt=row["prompt"],
            provider=row["provider"],
            input_image=row["input_image"],
            params=json.loads(row["params"] or "{}"),
            client_ref=row["client_ref"],
        )

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> JobRecord:
        artifacts = [Artifact(**a) for a in json.loads(row["artifacts"] or "[]")]
        return JobRecord(
            job_id=row["job_id"],
            batch_id=row["batch_id"],
            client_ref=row["client_ref"],
            type=JobType(row["type"]),
            provider=row["provider"],
            status=JobStatus(row["status"]),
            progress=row["progress"],
            artifacts=artifacts,
            error=row["error"],
            attempts=row["attempts"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
