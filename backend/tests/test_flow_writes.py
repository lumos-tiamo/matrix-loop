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
