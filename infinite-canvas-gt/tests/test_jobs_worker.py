import asyncio

from jobs.client import JobCanceled, JobExecutionError
from jobs.config import JobsConfig
from jobs.models import Artifact, JobSpec, JobStatus
from jobs.routing import JobRouter
from jobs.store import JobStore
from jobs.worker import WorkerPool


class FakeClient:
    """按 provider 决定成功/失败，记录被调用的 provider 顺序。"""

    def __init__(self, behavior):
        self.behavior = behavior  # provider -> "ok" | "fail" | "cancel"
        self.calls = []

    async def run(self, plan, spec, progress, cancel_check):
        self.calls.append(plan.provider)
        await progress(0.5)
        b = self.behavior.get(plan.provider, "fail")
        if b == "ok":
            return [Artifact(kind="image", url="/assets/output/x.png")]
        if b == "cancel":
            raise JobCanceled()
        raise JobExecutionError(f"{plan.provider} boom")


def _setup(behavior, max_retries=2):
    store = JobStore(":memory:")
    config = JobsConfig(base_dir="/tmp", max_retries=max_retries, concurrency=1)
    pool = WorkerPool(store, JobRouter(), FakeClient(behavior), config)
    return store, pool


def _seed(store, spec, provider):
    store.create_batch("b", [("j1", spec, provider)])
    return store.claim_next()  # attempts=1, status=running


def test_execute_success():
    store, pool = _setup({"modelscope": "ok"})
    claimed = _seed(store, JobSpec(type="text_to_image", prompt="x"), "modelscope")
    asyncio.run(pool._execute(claimed))
    rec = store.get("j1")
    assert rec.status == JobStatus.SUCCEEDED
    assert rec.artifacts[0].url == "/assets/output/x.png"


def test_execute_falls_back_to_secondary_provider():
    # 主力 jimeng 失败，降级 runninghub 成功（t2v 默认降级链含 runninghub）
    store, pool = _setup({"jimeng": "fail", "runninghub": "ok"})
    claimed = _seed(store, JobSpec(type="text_to_video", prompt="x"), "jimeng")
    asyncio.run(pool._execute(claimed))
    rec = store.get("j1")
    assert rec.status == JobStatus.SUCCEEDED
    assert pool._client.calls == ["jimeng", "runninghub"]


def test_execute_requeues_when_under_retry_limit():
    store, pool = _setup({"modelscope": "fail"}, max_retries=2)
    claimed = _seed(store, JobSpec(type="text_to_image", prompt="x"), "modelscope")
    # attempts=1 <= max_retries=2 → 重新入队
    asyncio.run(pool._execute(claimed))
    assert store.get("j1").status == JobStatus.QUEUED


def test_execute_fails_when_over_retry_limit():
    store, pool = _setup({"modelscope": "fail"}, max_retries=2)
    store.create_batch("b", [("j1", JobSpec(type="text_to_image", prompt="x"), "modelscope")])
    # 手动构造已达上限的 claimed（attempts=3 > max_retries=2）
    store.claim_next()
    claimed = {
        "job_id": "j1",
        "spec": JobSpec(type="text_to_image", prompt="x"),
        "provider": "modelscope",
        "attempts": 3,
    }
    asyncio.run(pool._execute(claimed))
    rec = store.get("j1")
    assert rec.status == JobStatus.FAILED
    assert "boom" in (rec.error or "")


def test_execute_respects_prior_cancel():
    store, pool = _setup({"modelscope": "ok"})
    claimed = _seed(store, JobSpec(type="text_to_image", prompt="x"), "modelscope")
    store.cancel("j1")  # 执行前就取消
    asyncio.run(pool._execute(claimed))
    rec = store.get("j1")
    assert rec.status == JobStatus.CANCELED
    assert pool._client.calls == []  # 未真正调用引擎
