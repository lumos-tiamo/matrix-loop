from app.models import Account, Endpoint, AudienceSegment, AccountSegment


def test_endpoint_and_segment_unique(session):
    session.add_all([Endpoint(name="Nina", url_pattern="linktr.ee/antalpha"),
                     AudienceSegment(label="海外投资者")])
    session.commit()
    assert session.query(Endpoint).one().name == "Nina"
    assert session.query(AudienceSegment).one().label == "海外投资者"


def test_account_composition_and_endpoint(session):
    ep = Endpoint(name="xaue", url_pattern="xaue.com")
    seg = AudienceSegment(label="crypto")
    session.add_all([ep, seg]); session.commit()
    acc = Account(platform="twitter", handle="@a", endpoint_id=ep.id)
    session.add(acc); session.commit()
    session.add(AccountSegment(account_id=acc.id, segment_id=seg.id, weight=0.7))
    session.commit()
    comp = session.query(AccountSegment).filter_by(account_id=acc.id).one()
    assert comp.weight == 0.7
    assert acc.endpoint_id == ep.id
