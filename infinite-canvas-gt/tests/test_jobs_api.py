from fastapi import FastAPI
from fastapi.testclient import TestClient

from jobs.api import create_jobs_router
from jobs.routing import JobRouter
from jobs.store import JobStore


def _client():
    store = JobStore(":memory:")
    app = FastAPI()
    app.include_router(create_jobs_router(store, JobRouter()))
    return TestClient(app), store


def test_submit_returns_ids_and_resolved_provider():
    client, _ = _client()
    r = client.post(
        "/api/jobs",
        json={"jobs": [
            {"type": "text_to_image", "prompt": "a cat", "client_ref": "r1"},
            {"type": "text_to_video", "prompt": "a dog"},
        ]},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["jobs"]) == 2
    assert body["jobs"][0]["provider"] == "modelscope"
    assert body["jobs"][0]["client_ref"] == "r1"
    assert body["jobs"][1]["provider"] == "jimeng"
    assert all(j["status"] == "queued" for j in body["jobs"])


def test_get_and_list_and_batch():
    client, _ = _client()
    r = client.post("/api/jobs", json={"jobs": [{"type": "text_to_image", "prompt": "x"}]})
    batch_id = r.json()["batch_id"]
    job_id = r.json()["jobs"][0]["job_id"]

    g = client.get(f"/api/jobs/{job_id}")
    assert g.status_code == 200
    assert g.json()["job_id"] == job_id

    lst = client.get("/api/jobs", params={"status": "queued"})
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    b = client.get(f"/api/jobs/batches/{batch_id}")
    assert b.status_code == 200
    assert b.json()["total"] == 1
    assert b.json()["done"] is False


def test_get_missing_404():
    client, _ = _client()
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/jobs/batches/nope").status_code == 404


def test_invalid_status_filter_400():
    client, _ = _client()
    assert client.get("/api/jobs", params={"status": "bogus"}).status_code == 400


def test_cancel():
    client, _ = _client()
    r = client.post("/api/jobs", json={"jobs": [{"type": "text_to_image", "prompt": "x"}]})
    job_id = r.json()["jobs"][0]["job_id"]
    c = client.post(f"/api/jobs/{job_id}/cancel")
    assert c.status_code == 200
    assert c.json()["status"] == "canceled"


def test_image_to_image_without_input_image_422():
    client, _ = _client()
    r = client.post("/api/jobs", json={"jobs": [{"type": "image_to_image", "prompt": "x"}]})
    assert r.status_code == 422
