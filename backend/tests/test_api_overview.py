from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem, LoopRun, Evaluation, Recommendation, Draft


def _seed(session):
    a1 = Account(platform="xiaohongshu", handle="@a1")
    a2 = Account(platform="twitter", handle="@a2")
    session.add_all([a1, a2]); session.commit()
    session.add_all([
        Snapshot(account_id=a1.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100000, engagement_rate=0.05),
        Snapshot(account_id=a1.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=112000, engagement_rate=0.06),
        Snapshot(account_id=a2.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=50000, engagement_rate=0.03),
        Snapshot(account_id=a2.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=49000, engagement_rate=0.03),
    ])
    r1 = LoopRun(account_id=a1.id, status="ok")
    r1.evaluation = Evaluation(account_id=a1.id, composite_score=88.0, breakdown={"growth": 90, "engagement": 80, "commercial": 60, "positioning": 92})
    r1.recommendations.append(Recommendation(kind="positioning", content="x", status="pending"))
    r1.drafts.append(Draft(kind="topic", content="t", review_status="pending"))
    r2 = LoopRun(account_id=a2.id, status="no_progress")
    r2.evaluation = Evaluation(account_id=a2.id, composite_score=40.0, breakdown={"growth": 20, "engagement": 50, "commercial": 40, "positioning": 30})
    session.add_all([r1, r2]); session.commit()
    return a1, a2


def test_overview_kpis_and_sections(client, session):
    a1, a2 = _seed(session)
    body = client.get("/overview").json()

    assert body["kpis"]["total_accounts"] == 2
    assert body["kpis"]["platforms"] == 2
    assert body["kpis"]["needs_attention"] == 1          # a2 no_progress
    assert body["kpis"]["pending_review"] == 2           # 1 rec + 1 draft pending
    assert body["kpis"]["avg_score"] == 64.0             # (88+40)/2

    plats = {p["platform"]: p for p in body["platform_health"]}
    assert plats["xiaohongshu"]["growth"] == 90
    assert plats["twitter"]["positioning"] == 30

    # matrix-wide trend aggregated by date
    trend = {t["date"]: t for t in body["trend"]}
    assert trend["2026-07-01"]["followers"] == 150000    # 100k + 50k
    assert trend["2026-07-06"]["followers"] == 161000    # 112k + 49k

    # alerts include the no_progress account
    kinds = {(a["account_id"], a["kind"]) for a in body["alerts"]}
    assert (a2.id, "no_progress") in kinds

    # top movers: a1 +12000, a2 -1000
    movers = {m["account_id"]: m["delta_followers"] for m in body["top_movers"]}
    assert movers[a1.id] == 12000
    assert movers[a2.id] == -1000

    dist = body["positioning_distribution"]
    assert dist["clear"] == 1 and dist["scattered"] == 1   # a1 pos 92 clear, a2 pos 30 scattered

    # pending-drafts alert exists for a1
    assert any(al["account_id"] == a1.id and al["kind"] == "pending_drafts" for al in body["alerts"])


def test_overview_empty_db(client):
    body = client.get("/overview").json()
    assert body["kpis"]["total_accounts"] == 0
    assert body["kpis"]["avg_score"] == 0.0
    assert body["platform_health"] == []
    assert body["trend"] == []
    assert body["positioning_distribution"] == {"clear": 0, "ok": 0, "scattered": 0}
