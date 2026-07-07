from datetime import datetime, timezone

from app.models import Account, Snapshot, Endpoint, AudienceSegment, AccountSegment
from app.flow.build import build_flow


def _acct(session, handle, followers, endpoint_id=None):
    acc = Account(platform="twitter", handle=handle, endpoint_id=endpoint_id)
    session.add(acc); session.commit()
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=followers))
    session.commit()
    return acc


def test_flow_edges_follower_weighted(session):
    nina = Endpoint(name="Nina", url_pattern="linktr.ee/x"); session.add(nina); session.commit()
    crypto = AudienceSegment(label="crypto"); overseas = AudienceSegment(label="海外投资者")
    session.add_all([crypto, overseas]); session.commit()

    a = _acct(session, "@a", 10000, endpoint_id=nina.id)
    session.add_all([
        AccountSegment(account_id=a.id, segment_id=crypto.id, weight=0.6),
        AccountSegment(account_id=a.id, segment_id=overseas.id, weight=0.4),
    ])
    session.commit()

    flow = build_flow(session)
    names = {n["name"] for n in flow["nodes"]}
    assert "acct:@a" in names and "seg:crypto" in names and "ep:Nina" in names
    links = {(l["source"], l["target"]): l["value"] for l in flow["links"]}
    # account -> segment weighted by follower share
    assert links[("acct:@a", "seg:crypto")] == 6000
    assert links[("acct:@a", "seg:海外投资者")] == 4000
    # segment -> endpoint (account routes whole flow to its endpoint)
    assert links[("seg:crypto", "ep:Nina")] == 6000
    assert links[("seg:海外投资者", "ep:Nina")] == 4000


def test_flow_unrouted_account_goes_to_placeholder(session):
    seg = AudienceSegment(label="crypto"); session.add(seg); session.commit()
    a = _acct(session, "@b", 5000, endpoint_id=None)   # no endpoint
    session.add(AccountSegment(account_id=a.id, segment_id=seg.id, weight=1.0)); session.commit()
    flow = build_flow(session)
    links = {(l["source"], l["target"]): l["value"] for l in flow["links"]}
    assert links[("seg:crypto", "ep:未定向")] == 5000


def test_flow_empty_is_valid(session):
    flow = build_flow(session)
    assert flow == {"nodes": [], "links": []}
