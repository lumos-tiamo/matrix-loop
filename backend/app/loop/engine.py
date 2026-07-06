from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentItem, Draft, Evaluation, LoopRun, Recommendation, Snapshot
from app.evaluation.scoring import ScoringConfig, evaluate_with_content
from app.analysis.content import hit_content


@dataclass(frozen=True)
class LoopConfig:
    no_progress_limit: int = 3     # 连续 N 轮复合分未提升 -> status=no_progress
    min_improvement: float = 0.5   # 复合分提升需 > 该值才算"改善"


def _gather(session: Session, account_id: int):
    snaps = session.scalars(select(Snapshot).where(Snapshot.account_id == account_id)).all()
    content = session.scalars(select(ContentItem).where(ContentItem.account_id == account_id)).all()
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


def run_loop(session: Session, account, *, llm_client=None, cfg: LoopConfig | None = None,
             scoring_cfg: ScoringConfig | None = None) -> LoopRun:
    cfg = cfg or LoopConfig()
    snapshots, content = _gather(session, account.id)

    analysis = None
    if llm_client is not None:
        from app.evaluation.scoring import evaluate_with_analysis
        result, analysis = evaluate_with_analysis(account, snapshots, content, llm_client, cfg=scoring_cfg)
    else:
        result = evaluate_with_content(account, snapshots, content, cfg=scoring_cfg)

    diagnosis, recs, drafts = _build_outputs(result, analysis, content)

    run = LoopRun(
        account_id=account.id,
        diagnosis=diagnosis,
        verify_result={"baseline": True, "improved": False, "delta": 0.0},
        tokens_cost=0,
        status="ok",
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
