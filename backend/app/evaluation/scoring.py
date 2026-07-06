from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringConfig:
    target_growth_rate: float = 0.10       # 期望评估窗口内涨粉比例
    target_engagement_rate: float = 0.05   # 期望互动率
    target_conversions: float = 10          # 期望转化/线索数


@dataclass
class EvaluationResult:
    composite_score: float
    breakdown: dict


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def growth_score(snapshots, cfg: ScoringConfig) -> float:
    if not cfg.target_growth_rate:
        return 0.0
    snaps = sorted((s for s in snapshots if s.followers is not None), key=lambda s: s.ts)
    # snaps[0].followers == 0: zero baseline makes rate undefined; treat as no growth
    if len(snaps) < 2 or snaps[0].followers == 0:
        return 0.0
    rate = (snaps[-1].followers - snaps[0].followers) / snaps[0].followers
    # Negative growth (shrinkage) is intentionally clamped to 0.0; plan 3 can
    # consult raw snapshot deltas to distinguish shrinkage from stagnation.
    return round(_clamp(rate / cfg.target_growth_rate * 100), 2)


def engagement_score(latest, cfg: ScoringConfig) -> float:
    if not cfg.target_engagement_rate:
        return 0.0
    er = getattr(latest, "engagement_rate", None) or 0.0
    return round(_clamp(er / cfg.target_engagement_rate * 100), 2)


def commercial_score(latest, cfg: ScoringConfig) -> float:
    if not cfg.target_conversions:
        return 0.0
    conv = getattr(latest, "conversions", None) or 0
    return round(_clamp(conv / cfg.target_conversions * 100), 2)


def evaluate_account(account, snapshots, positioning_score: float, cfg: ScoringConfig | None = None) -> EvaluationResult:
    cfg = cfg or ScoringConfig()
    ordered = sorted(snapshots, key=lambda s: s.ts) if snapshots else []
    latest = ordered[-1] if ordered else None

    sub = {
        "growth": growth_score(snapshots, cfg),
        "engagement": engagement_score(latest, cfg),
        "commercial": commercial_score(latest, cfg),
        "positioning": round(_clamp(positioning_score), 2),
    }

    weights = account.objective_weights or {}
    total_w = sum(weights.get(k, 0.0) for k in sub) or 1.0
    composite = sum(sub[k] * weights.get(k, 0.0) for k in sub) / total_w
    return EvaluationResult(composite_score=round(composite, 2), breakdown=sub)


def evaluate_with_content(account, snapshots, content_items, cfg: ScoringConfig | None = None) -> EvaluationResult:
    """便捷入口：用确定性内容分析的定位代理分，喂给 evaluate_account。

    plan 3 将用 LLM 定位清晰度替换/增强这里的 positioning_score。
    """
    from app.analysis.content import positioning_proxy_score

    positioning = positioning_proxy_score(content_items)
    return evaluate_account(account, snapshots, positioning_score=positioning, cfg=cfg)


def evaluate_with_analysis(account, snapshots, content_items, client, cfg: ScoringConfig | None = None):
    """LLM path: use analyze_positioning's clarity as the positioning sub-score.

    Returns (EvaluationResult, AnalysisResult). The AnalysisResult carries
    positioning_label / content_direction / suggested_topics for the Loop's
    later diagnosis + draft steps.
    """
    from app.analysis.llm import analyze_positioning

    analysis = analyze_positioning(account, content_items, client)
    result = evaluate_account(account, snapshots, positioning_score=analysis.positioning_clarity, cfg=cfg)
    return result, analysis
