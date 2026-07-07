from app.models import Account, Endpoint, AudienceSegment, AccountSegment
from app.flow.match import match_endpoint


def test_match_endpoint_by_url_substring(session):
    eps = [Endpoint(name="Nina", url_pattern="linktr.ee/antalpha"), Endpoint(name="xaue", url_pattern="xaue.com")]
    assert match_endpoint("https://xaue.com/protocol", eps).name == "xaue"
    assert match_endpoint("https://example.com", eps) is None


def test_create_segment_and_endpoint(client, session):
    assert client.post("/segments", json={"label": "crypto"}).status_code == 201
    assert client.post("/endpoints", json={"name": "Nina", "url_pattern": "linktr.ee/x"}).status_code == 201
    assert session.query(AudienceSegment).count() == 1
    assert session.query(Endpoint).count() == 1


def test_set_account_composition_and_endpoint(client, session):
    ep = Endpoint(name="Nina"); seg = AudienceSegment(label="crypto")
    session.add_all([ep, seg]); session.commit()
    acc = Account(platform="twitter", handle="@a"); session.add(acc); session.commit()

    r1 = client.post(f"/accounts/{acc.id}/segments", json={"segments": [{"segment_id": seg.id, "weight": 0.8}]})
    assert r1.status_code == 200
    assert session.query(AccountSegment).filter_by(account_id=acc.id).one().weight == 0.8

    r2 = client.post(f"/accounts/{acc.id}/endpoint", json={"endpoint_id": ep.id})
    assert r2.status_code == 200
    session.refresh(acc)
    assert acc.endpoint_id == ep.id


def test_composition_rejects_unknown_segment(client, session):
    seg = AudienceSegment(label="crypto")
    session.add(seg); session.commit()
    acc = Account(platform="twitter", handle="@b"); session.add(acc); session.commit()
    # give the account a valid composition first
    session.add(AccountSegment(account_id=acc.id, segment_id=seg.id, weight=1.0))
    session.commit()

    bogus_id = seg.id + 9999
    r = client.post(f"/accounts/{acc.id}/segments", json={"segments": [{"segment_id": bogus_id, "weight": 1.0}]})
    assert r.status_code == 422
    # existing composition must be untouched
    remaining = session.query(AccountSegment).filter_by(account_id=acc.id).all()
    assert len(remaining) == 1
    assert remaining[0].segment_id == seg.id


def test_composition_rejects_duplicate_segment(client, session):
    seg = AudienceSegment(label="defi")
    session.add(seg); session.commit()
    acc = Account(platform="twitter", handle="@c"); session.add(acc); session.commit()

    r = client.post(
        f"/accounts/{acc.id}/segments",
        json={"segments": [{"segment_id": seg.id, "weight": 0.5}, {"segment_id": seg.id, "weight": 0.5}]},
    )
    assert r.status_code == 422
    assert "duplicate" in r.json()["detail"]


def test_duplicate_segment_returns_409(client, session):
    r1 = client.post("/segments", json={"label": "nft"})
    assert r1.status_code == 201
    r2 = client.post("/segments", json={"label": "nft"})
    assert r2.status_code == 409


def test_set_endpoint_unknown_422(client, session):
    acc = Account(platform="twitter", handle="@d"); session.add(acc); session.commit()
    r = client.post(f"/accounts/{acc.id}/endpoint", json={"endpoint_id": 99999})
    assert r.status_code == 422
    assert "endpoint not found" in r.json()["detail"]


def test_list_segments_returns_created(client):
    client.post("/segments", json={"label": "crypto"})
    client.post("/segments", json={"label": "宝妈"})
    resp = client.get("/segments")
    assert resp.status_code == 200
    labels = {s["label"] for s in resp.json()}
    assert {"crypto", "宝妈"} <= labels
    assert all("id" in s and "label" in s for s in resp.json())


def test_list_endpoints_returns_created(client):
    client.post("/endpoints", json={"name": "Nina", "url_pattern": "linktr.ee/nina"})
    resp = client.get("/endpoints")
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["name"] == "Nina" and r["url_pattern"] == "linktr.ee/nina" for r in rows)
    assert all({"id", "name", "url_pattern"} <= set(r) for r in rows)


def test_demo_reset_wires_flow_for_existing_accounts(client, session):
    from app.models import Account, Snapshot
    from datetime import datetime, timezone
    for h in ("@money_talk", "@tech_daily"):
        acc = Account(platform="twitter", handle=h,
                      objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
        session.add(acc); session.commit()
        session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=1000))
        session.commit()

    resp = client.post("/demo/reset")
    assert resp.status_code == 200
    body = resp.json()
    assert body["endpoints"] >= 1 and body["segments"] >= 1

    flow = client.get("/flow").json()
    names = {n["name"] for n in flow["nodes"]}
    assert any(n.startswith("seg:") for n in names)
    assert any(n.startswith("ep:") for n in names)


def test_demo_reset_is_idempotent(client, session):
    from app.models import Account, Snapshot
    from datetime import datetime, timezone
    acc = Account(platform="twitter", handle="@money_talk",
                  objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc); session.commit()
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=1000))
    session.commit()

    first = client.post("/demo/reset").json()
    second = client.post("/demo/reset").json()
    assert first["endpoints"] == second["endpoints"]
    assert first["segments"] == second["segments"]
    segs = client.get("/segments").json()
    assert len({s["label"] for s in segs}) == len(segs)  # no dup labels
