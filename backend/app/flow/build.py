from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountSegment, AudienceSegment, Endpoint, Snapshot

UNROUTED = "未定向"


def _latest_followers(session: Session, account_id: int) -> int:
    snap = session.scalars(
        select(Snapshot).where(Snapshot.account_id == account_id)
        .order_by(Snapshot.ts.desc(), Snapshot.id.desc())
    ).first()
    return (snap.followers or 0) if snap else 0


def build_flow(session: Session) -> dict:
    accounts = list(session.scalars(select(Account).order_by(Account.id)).all())
    segments = {s.id: s.label for s in session.scalars(select(AudienceSegment)).all()}
    endpoints = {e.id: e.name for e in session.scalars(select(Endpoint)).all()}

    links: dict[tuple[str, str], float] = {}
    used: set[str] = set()

    def add(src: str, tgt: str, val: float) -> None:
        if val <= 0:
            return
        links[(src, tgt)] = links.get((src, tgt), 0.0) + val
        used.add(src); used.add(tgt)

    for a in accounts:
        comps = list(session.scalars(select(AccountSegment).where(AccountSegment.account_id == a.id)).all())
        if not comps:
            continue
        followers = _latest_followers(session, a.id)
        if followers <= 0:
            continue
        wsum = sum(c.weight for c in comps) or 1.0
        ep_name = endpoints.get(a.endpoint_id, UNROUTED) if a.endpoint_id else UNROUTED
        acct_node = f"acct:{a.handle}"
        for c in comps:
            label = segments.get(c.segment_id)
            if label is None:
                continue
            flow = followers * c.weight / wsum
            seg_node = f"seg:{label}"
            add(acct_node, seg_node, flow)
            add(seg_node, f"ep:{ep_name}", flow)

    nodes = [{"name": n} for n in sorted(used)]
    link_list = [{"source": s, "target": t, "value": round(v)} for (s, t), v in sorted(links.items())]
    return {"nodes": nodes, "links": link_list}
