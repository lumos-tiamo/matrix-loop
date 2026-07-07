"""Demo flow dataset (endpoints / audience segments / account routing) + reset helper.

Single source of truth shared by seed_demo.py and POST /demo/reset. reset_flow is
idempotent: existing segments/endpoints are reused by label/name (no duplicates),
and each named account's composition is fully replaced with the demo wiring.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountSegment, AudienceSegment, Endpoint

DEMO_ENDPOINTS: list[tuple[str, str | None]] = [
    ("Nina", "linktr.ee/nina"),
    ("xaue", "xaue.com"),
    ("私域社群", "t.me/matrixloop"),
]
DEMO_SEGMENTS: list[str] = ["crypto", "海外投资者", "宝妈", "打工人群"]
DEMO_ASSIGN: dict[str, tuple[str | None, list[tuple[str, float]]]] = {
    "@money_talk": ("Nina", [("crypto", 0.6), ("海外投资者", 0.4)]),
    "@tech_daily": ("xaue", [("crypto", 0.5), ("打工人群", 0.5)]),
    "@beauty_lab": ("私域社群", [("宝妈", 0.7), ("打工人群", 0.3)]),
    "@travel_vlog": (None, [("海外投资者", 0.4), ("打工人群", 0.6)]),
    "@fit_coach": ("私域社群", [("打工人群", 1.0)]),
}


def reset_flow(session: Session) -> dict:
    """Idempotently (re)apply the demo flow wiring. Returns counts. Safe to call repeatedly."""
    endpoints: dict[str, Endpoint] = {}
    for name, pat in DEMO_ENDPOINTS:
        ep = session.scalar(select(Endpoint).where(Endpoint.name == name))
        if ep is None:
            ep = Endpoint(name=name, url_pattern=pat)
            session.add(ep)
        else:
            ep.url_pattern = pat
        endpoints[name] = ep

    segments: dict[str, AudienceSegment] = {}
    for label in DEMO_SEGMENTS:
        seg = session.scalar(select(AudienceSegment).where(AudienceSegment.label == label))
        if seg is None:
            seg = AudienceSegment(label=label)
            session.add(seg)
        segments[label] = seg
    session.flush()  # assign ids before wiring

    accounts = {a.handle: a for a in session.scalars(select(Account)).all()}
    routed = 0
    for handle, (ep_name, comps) in DEMO_ASSIGN.items():
        acc = accounts.get(handle)
        if acc is None:
            continue
        acc.endpoint_id = endpoints[ep_name].id if ep_name else None
        session.query(AccountSegment).filter_by(account_id=acc.id).delete()
        for label, weight in comps:
            session.add(AccountSegment(account_id=acc.id, segment_id=segments[label].id, weight=weight))
        routed += 1
    session.commit()
    return {"endpoints": len(endpoints), "segments": len(segments), "routed": routed}
