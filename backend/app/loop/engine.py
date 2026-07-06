from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentItem, Draft, Evaluation, LoopRun, Recommendation, Snapshot
from app.evaluation.scoring import ScoringConfig, evaluate_with_content, evaluate_with_analysis
from app.analysis.content import hit_content


@dataclass(frozen=True)
class LoopConfig:
    # no_progress_limit: 需要 N 个历史轮次都已存在、且当前轮相比其中最旧一轮的复合分提升不超过
    # min_improvement 时判定 no_progress（即 N 个历史 + 当前 = N+1 轮持平）
    no_progress_limit: int = 3
    min_improvement: float = 0.5   # 复合分提升需 > 该值才算"改善"


def _gather(session: Session, account_id: int):
    snaps = session.scalars(select(Snapshot).where(Snapshot.account_id == account_id)).all()  # TODO(plan-8): add a date/count window for large histories
    content = session.scalars(select(ContentItem).where(ContentItem.account_id == account_id)).all()  # TODO(plan-8): add a date/count window for large histories
    return list(snaps), list(content)


def _build_outputs(result, analysis, content_items):
    recs: list[Recommendation] = []
    drafts: list[Draft] = []
    if analysis is not None:
        diagnosis = (
            f"定位「{analysis.positioning_label}」，清晰度 {analysis.positioning_clarity:.0f}/100。"
            f"{analysis.content_direction}"
        )
        recs.append(Recommendation(kind="positioning", content=f"聚焦定位：{analysis.positioning_label}"))
        recs.append(Recommendation(kind="content_direction", content=analysis.content_direction))
        drafts.extend(Draft(kind="topic", content=t) for t in analysis.suggested_topics)
    else:
        pos = result.breakdown.get("positioning", 0.0)
        diagnosis = f"确定性评估：复合价值分 {result.composite_score:.0f}/100，定位清晰度代理 {pos:.0f}/100。"
        recs.append(Recommendation(
            kind="content_direction",
            content="定位偏散，建议收敛选题、聚焦单一垂类" if pos < 60 else "定位清晰，保持方向并提升优质内容产量",
        ))
    hits = hit_content(content_items)
    if hits:
        recs.append(Recommendation(
            kind="cadence",
            content=f"复制 {len(hits)} 条爆文的选题结构，提高高表现内容的产出频率",
        ))
    return diagnosis, recs, drafts


def _previous_run(session: Session, account_id: int) -> LoopRun | None:
    stmt = (
        select(LoopRun)
        .where(LoopRun.account_id == account_id)
        .order_by(LoopRun.ts.desc(), LoopRun.id.desc())
    )
    return session.scalars(stmt).first()


def _verify(prev: LoopRun | None, current_composite: float, cfg: LoopConfig) -> dict:
    if prev is None or prev.evaluation is None:
        return {"baseline": True, "improved": False, "delta": 0.0}
    delta = round(current_composite - prev.evaluation.composite_score, 2)
    return {"baseline": False, "improved": delta > cfg.min_improvement, "delta": delta}


def _mark_prev_recommendations(prev: LoopRun | None, verify: dict) -> None:
    if prev is None or verify.get("baseline"):
        return
    outcome = "worked" if verify["improved"] else "failed"
    for rec in prev.recommendations:
        if rec.status == "adopted":
            rec.status = outcome


def _status(session: Session, account_id: int, current_composite: float, cfg: LoopConfig) -> str:
    stmt = (
        select(Evaluation)
        .join(LoopRun, Evaluation.loop_run_id == LoopRun.id)
        .where(LoopRun.account_id == account_id)
        .order_by(LoopRun.ts.desc(), LoopRun.id.desc())
        .limit(cfg.no_progress_limit)
    )
    prior = [e.composite_score for e in session.scalars(stmt)]
    if len(prior) >= cfg.no_progress_limit:
        oldest_in_window = prior[cfg.no_progress_limit - 1]
        if round(current_composite - oldest_in_window, 2) <= cfg.min_improvement:
            return "no_progress"
    return "ok"


def run_loop(session: Session, account, *, llm_client=None, cfg: LoopConfig | None = None,
             scoring_cfg: ScoringConfig | None = None) -> LoopRun:
    cfg = cfg or LoopConfig()
    try:
        snapshots, content = _gather(session, account.id)

        analysis = None
        if llm_client is not None:
            result, analysis = evaluate_with_analysis(account, snapshots, content, llm_client, cfg=scoring_cfg)
        else:
            result = evaluate_with_content(account, snapshots, content, cfg=scoring_cfg)

        diagnosis, recs, drafts = _build_outputs(result, analysis, content)

        prev = _previous_run(session, account.id)
        verify = _verify(prev, result.composite_score, cfg)
        _mark_prev_recommendations(prev, verify)
        status = _status(session, account.id, result.composite_score, cfg)

        run = LoopRun(
            account_id=account.id,
            diagnosis=diagnosis,
            verify_result=verify,
            tokens_cost=0,  # TODO(plan-8): wire real token usage from LLMClient
            status=status,
        )
        run.evaluation = Evaluation(
            account_id=account.id,
            composite_score=result.composite_score,
            breakdown=result.breakdown,
        )
        run.recommendations = recs
        run.drafts = drafts
        session.add(run)
        session.commit()
        return run
    except Exception:
        session.rollback()
        raise
