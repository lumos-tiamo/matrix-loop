"""统一「内容作业」API —— loop 唯一需要对接的稳定契约。

用法：POST /api/jobs 提交一批 → GET /api/jobs/{id} 轮询到 succeeded → 读 artifacts[].path。
"""

from __future__ import annotations

import uuid
from collections import Counter
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .models import JobRecord, JobStatus, JobSubmit
from .routing import JobRouter
from .store import JobStore


class SubmittedJob(BaseModel):
    job_id: str
    client_ref: Optional[str] = None
    status: str
    provider: str
    type: str


class SubmitResult(BaseModel):
    batch_id: str
    jobs: List[SubmittedJob]


class BatchSummary(BaseModel):
    batch_id: str
    total: int
    counts: dict
    done: bool


def create_jobs_router(store: JobStore, router: JobRouter) -> APIRouter:
    api = APIRouter(prefix="/api/jobs", tags=["jobs"])

    @api.post("", response_model=SubmitResult)
    @api.post("/", response_model=SubmitResult, include_in_schema=False)
    async def submit_jobs(payload: JobSubmit) -> SubmitResult:
        batch_id = uuid.uuid4().hex
        specs_with_ids = []
        stubs: List[SubmittedJob] = []
        for spec in payload.jobs:
            job_id = "job_" + uuid.uuid4().hex
            provider = router.resolve(spec).provider
            specs_with_ids.append((job_id, spec, provider))
            stubs.append(
                SubmittedJob(
                    job_id=job_id,
                    client_ref=spec.client_ref,
                    status=JobStatus.QUEUED.value,
                    provider=provider,
                    type=spec.type.value,
                )
            )
        store.create_batch(batch_id, specs_with_ids)
        return SubmitResult(batch_id=batch_id, jobs=stubs)

    @api.get("/batches/{batch_id}", response_model=BatchSummary)
    async def batch_summary(batch_id: str) -> BatchSummary:
        records = store.list(batch_id=batch_id, limit=1000)
        if not records:
            raise HTTPException(status_code=404, detail="batch not found")
        counts = Counter(r.status.value for r in records)
        terminal = {
            JobStatus.SUCCEEDED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELED.value,
        }
        done = all(r.status.value in terminal for r in records)
        return BatchSummary(
            batch_id=batch_id, total=len(records), counts=dict(counts), done=done
        )

    @api.get("", response_model=List[JobRecord])
    async def list_jobs(
        status: Optional[str] = Query(default=None),
        batch_id: Optional[str] = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> List[JobRecord]:
        if status is not None and status not in {s.value for s in JobStatus}:
            raise HTTPException(status_code=400, detail=f"invalid status {status!r}")
        return store.list(status=status, batch_id=batch_id, limit=limit)

    @api.get("/{job_id}", response_model=JobRecord)
    async def get_job(job_id: str) -> JobRecord:
        rec = store.get(job_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="job not found")
        return rec

    @api.post("/{job_id}/cancel", response_model=JobRecord)
    async def cancel_job(job_id: str) -> JobRecord:
        rec = store.get(job_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="job not found")
        store.cancel(job_id)
        return store.get(job_id)

    return api
