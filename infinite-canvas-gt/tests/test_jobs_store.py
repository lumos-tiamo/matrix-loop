from jobs.models import Artifact, JobSpec, JobStatus
from jobs.store import JobStore


def _store():
    return JobStore(":memory:")


def _spec(t="text_to_image", **kw):
    return JobSpec(type=t, prompt="x", **kw)


def test_create_and_get():
    s = _store()
    s.create_batch("b1", [("job_1", _spec(client_ref="ref1"), "modelscope")])
    rec = s.get("job_1")
    assert rec is not None
    assert rec.status == JobStatus.QUEUED
    assert rec.provider == "modelscope"
    assert rec.client_ref == "ref1"
    assert rec.batch_id == "b1"


def test_claim_is_atomic_and_sets_running():
    s = _store()
    s.create_batch("b", [("j1", _spec(), "modelscope"), ("j2", _spec(), "jimeng")])
    c1 = s.claim_next()
    c2 = s.claim_next()
    c3 = s.claim_next()
    assert {c1["job_id"], c2["job_id"]} == {"j1", "j2"}
    assert c3 is None  # 全部被领走
    assert s.get("j1").status == JobStatus.RUNNING
    assert s.get("j1").attempts == 1


def test_claim_preserves_spec():
    s = _store()
    spec = _spec("image_to_video", input_image="/assets/output/a.png", params={"model": "3.0"})
    s.create_batch("b", [("j1", spec, "jimeng")])
    claimed = s.claim_next()
    assert claimed["spec"].type.value == "image_to_video"
    assert claimed["spec"].input_image == "/assets/output/a.png"
    assert claimed["spec"].params == {"model": "3.0"}
    assert claimed["provider"] == "jimeng"


def test_succeeded_stores_artifacts():
    s = _store()
    s.create_batch("b", [("j1", _spec(), "modelscope")])
    s.claim_next()
    s.set_succeeded("j1", [Artifact(kind="image", path="/abs/x.png", url="/assets/output/x.png")])
    rec = s.get("j1")
    assert rec.status == JobStatus.SUCCEEDED
    assert rec.progress == 1.0
    assert rec.artifacts[0].path == "/abs/x.png"
    assert rec.artifacts[0].kind == "image"


def test_requeue_then_reclaim_increments_attempts():
    s = _store()
    s.create_batch("b", [("j1", _spec(), "modelscope")])
    s.claim_next()  # attempts -> 1
    s.requeue("j1", "boom")
    assert s.get("j1").status == JobStatus.QUEUED
    again = s.claim_next()  # attempts -> 2
    assert again["attempts"] == 2


def test_cancel_only_before_terminal():
    s = _store()
    s.create_batch("b", [("j1", _spec(), "x".replace("x", "modelscope"))])
    assert s.cancel("j1") is True
    assert s.get("j1").status == JobStatus.CANCELED
    # 已终态无法再取消
    assert s.cancel("j1") is False


def test_recover_stuck_requeues_running():
    s = _store()
    s.create_batch("b", [("j1", _spec(), "modelscope"), ("j2", _spec(), "modelscope")])
    s.claim_next()
    s.claim_next()
    assert s.get("j1").status == JobStatus.RUNNING
    n = s.recover_stuck()
    assert n == 2
    assert s.get("j1").status == JobStatus.QUEUED


def test_list_filters():
    s = _store()
    s.create_batch("b1", [("j1", _spec(), "modelscope")])
    s.create_batch("b2", [("j2", _spec(), "jimeng")])
    s.claim_next()  # j1 running
    assert {r.job_id for r in s.list(batch_id="b1")} == {"j1"}
    assert {r.job_id for r in s.list(status="queued")} == {"j2"}
    assert len(s.list()) == 2
