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
