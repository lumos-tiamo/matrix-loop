"""Content calibration loop — blind prediction + rubric scoring → publish gate → T+Nd review
→ rubric evolution. Adapted from xiaobei's content-calibrator for matrix-loop's code service.

Three non-negotiable principles (kept from the source methodology):
  1. Blind prediction — the prediction is written before any real data exists, then frozen
     (Calibration.locked_at). We never edit predicted[] after locking.
  2. Upgrade = full re-score — a rubric version bump invalidates old scores; stale-versioned
     calibrations are surfaced for re-scoring (needs_rescore()).
  3. The rubric is a workbench — evolve_rubric mutates it and bumps the version; history lives
     in git + the rubric changelog, not in dead dimensions.

Like the rest of the loop, everything degrades gracefully: with no LLM client the scorer uses
a deterministic text-heuristic proxy (mirrors evaluate_with_content vs evaluate_with_analysis).
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calibration import rubric as rubric_mod
from app.models import Calibration, ContentItem, Snapshot, VideoAsset, Draft, _utcnow

logger = logging.getLogger(__name__)

# metrics we blind-predict and later score against reality
PREDICT_METRICS = ("views", "engagement_rate")
DEFAULT_BASELINE_VIEWS = 500        # cold-start baseline when the account has no history
DEFAULT_ENGAGEMENT_RATE = 0.04


# --------------------------------------------------------------------------- scoring

def _script_for(session: Session, asset: VideoAsset) -> str:
    if asset.script_draft_id is None:
        return ""
    d = session.get(Draft, asset.script_draft_id)
    return (d.content if d else "") or ""


def _deterministic_scores(script: str, rubric: dict) -> tuple[dict, str]:
    """Cheap text-heuristic proxy per rubric dimension (0-100). Only used when no LLM is
    configured — it is intentionally coarse, the LLM path is the real scorer."""
    text = (script or "").strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    n_chars = len(text)
    first = lines[0] if lines else ""
    has_question = any(c in first for c in "?？")
    has_number = any(c.isdigit() for c in first)
    has_cta = any(k in text for k in ("关注", "点击", "follow", "link", "私信", "评论", "主页"))
    distinct_words = len(set(text.split()))

    def clamp(x): return max(0.0, min(100.0, x))
    dim = {
        "hook": clamp(45 + (25 if has_question else 0) + (20 if has_number else 0) + min(10, len(first) / 4)),
        "value": clamp(40 + min(45, n_chars / 12)),
        "clarity": clamp(80 - max(0, len(lines) - 8) * 4),
        "differentiation": clamp(40 + min(45, distinct_words / 3)),
        "cta": clamp(35 + (50 if has_cta else 0)),
    }
    scores = {}
    for d in rubric.get("dimensions", []):
        scores[d["key"]] = round(dim.get(d["key"], 55.0), 1)
    return scores, "deterministic text-heuristic proxy (no LLM configured)"


def _llm_scores(script: str, brief, rubric: dict, client) -> tuple[dict, str]:
    from app.analysis.llm import _extract_json
    dims = "\n".join(f"- {d['key']} ({d['label']}, 权重{d['weight']}): {d['guide']}"
                     for d in rubric.get("dimensions", []))
    system = ("你是资深短视频内容评审。只依据脚本本身盲评质量,不得臆测真实数据。"
              "对每个维度给 0-100 分,并给一句总评。严格输出 JSON。")
    prompt = (f"评分维度:\n{dims}\n\n"
              f"频道定位: {getattr(brief, 'main_direction', '') or '-'} / "
              f"语气 {getattr(brief, 'tone', '') or '-'}\n\n"
              f"待评脚本:\n{script[:4000]}\n\n"
              f'输出: {{"scores": {{"<key>": <0-100>, ...}}, "note": "<一句总评>"}}')
    raw = client.complete(system=system, prompt=prompt)
    data = json.loads(_extract_json(raw))
    scores = {}
    for d in rubric.get("dimensions", []):
        scores[d["key"]] = round(float(data.get("scores", {}).get(d["key"], 55.0)), 1)
    return scores, str(data.get("note", ""))[:400]


def _weighted(scores: dict, rubric: dict) -> float:
    dims = rubric.get("dimensions", [])
    total_w = sum(d.get("weight", 0.0) for d in dims) or 1.0
    return round(sum(scores.get(d["key"], 0.0) * d.get("weight", 0.0) for d in dims) / total_w, 2)


def _account_baseline(session: Session, account_id: int) -> dict:
    """Recent per-post baseline for this account (median views, latest engagement_rate) — the
    platform-specific prediction input. Falls back to cold-start defaults."""
    rows = list(session.scalars(
        select(ContentItem).where(ContentItem.account_id == account_id)
        .order_by(ContentItem.published_at.desc().nullslast()).limit(20)
    ))
    views = sorted(r.views for r in rows if r.views is not None)
    baseline_views = views[len(views) // 2] if views else DEFAULT_BASELINE_VIEWS
    latest_snap = session.scalar(
        select(Snapshot).where(Snapshot.account_id == account_id).order_by(Snapshot.ts.desc()).limit(1)
    )
    er = (latest_snap.engagement_rate if latest_snap and latest_snap.engagement_rate else None) \
        or DEFAULT_ENGAGEMENT_RATE
    return {"baseline_views": int(baseline_views), "engagement_rate": round(float(er), 4)}


def score_and_predict(session: Session, asset: VideoAsset, *, brief=None, client=None) -> Calibration:
    """Blind-score `asset` against the current rubric and predict its metrics, then FREEZE.
    Idempotent: returns the existing calibration if one already exists for this asset."""
    existing = session.scalar(select(Calibration).where(Calibration.video_asset_id == asset.id))
    if existing is not None:
        return existing

    rubric = rubric_mod.get_rubric(session)
    script = _script_for(session, asset)
    if brief is None:
        from app.models import ChannelBrief
        brief = session.scalar(select(ChannelBrief).where(ChannelBrief.account_id == asset.account_id))

    if client is not None:
        try:
            scores, note = _llm_scores(script, brief, rubric, client)
        except Exception as exc:  # noqa: BLE001 - LLM must not break the gate; fall back
            logger.warning("calibration LLM scoring failed, using deterministic proxy: %s", exc)
            scores, note = _deterministic_scores(script, rubric)
    else:
        scores, note = _deterministic_scores(script, rubric)

    quality = _weighted(scores, rubric)
    threshold = float(rubric.get("threshold", 60.0))
    baseline = _account_baseline(session, asset.account_id)
    # quality above threshold predicts an uplift; below predicts a discount (blind, monotonic)
    factor = quality / max(1.0, threshold)
    predicted = {
        "views": int(baseline["baseline_views"] * factor),
        "engagement_rate": round(baseline["engagement_rate"] * factor, 4),
    }

    cal = Calibration(
        video_asset_id=asset.id, account_id=asset.account_id,
        rubric_version=rubric.get("version", "v1"),
        quality_score=quality, breakdown={"scores": scores, "baseline": baseline},
        predicted=predicted, prediction_note=note,
        gate_passed=bool(quality >= threshold), status="predicted",
        locked_at=_utcnow(),
    )
    session.add(cal)
    session.commit()
    return cal


# --------------------------------------------------------------------------- gate

def gate(session: Session, asset: VideoAsset, *, brief=None, client=None) -> Calibration:
    """Ensure a calibration exists for `asset` and return it. Callers read `.gate_passed`
    to decide whether to publish — the quality門 borrowed from content-calibrator."""
    return score_and_predict(session, asset, brief=brief, client=client)


# --------------------------------------------------------------------------- review (T+Nd)

def _actual_metrics(session: Session, asset_id: int) -> dict | None:
    """Real interaction data for a published work, from the ContentItem linked to the asset."""
    item = session.scalar(
        select(ContentItem).where(ContentItem.video_asset_id == asset_id)
        .order_by(ContentItem.published_at.desc().nullslast()).limit(1)
    )
    if item is None or item.views is None:
        return None
    inter = (item.likes or 0) + (item.comments or 0) + (item.saves or 0)
    er = round(inter / item.views, 4) if item.views else 0.0
    return {"views": int(item.views), "engagement_rate": er}


def _pct_error(pred: float, actual: float) -> float:
    if pred == 0:
        return 0.0 if actual == 0 else 100.0
    return round((actual - pred) / pred * 100, 1)


def review(session: Session, cal: Calibration, *, actual: dict | None = None) -> Calibration:
    """Fill actual metrics, compute per-metric signed % error + aggregate mean-abs error, and
    mark reviewed. `actual` may be passed in (tests/manual) or pulled from ContentItem."""
    if actual is None:
        actual = _actual_metrics(session, cal.video_asset_id)
    if not actual:
        raise ValueError("no actual metrics available yet for this work")
    err = {m: _pct_error(float(cal.predicted.get(m, 0)), float(actual.get(m, 0)))
           for m in PREDICT_METRICS if m in actual}
    cal.actual = actual
    cal.error = err
    cal.calibration_error = round(sum(abs(v) for v in err.values()) / len(err), 1) if err else None
    cal.status = "reviewed"
    cal.reviewed_at = _utcnow()
    session.commit()
    return cal


def pending_reviews(session: Session, *, min_age_days: int = 3) -> list[Calibration]:
    """Published works whose prediction was locked ≥ min_age_days ago and not yet reviewed."""
    cutoff = _utcnow() - timedelta(days=min_age_days)
    return list(session.scalars(
        select(Calibration).where(
            Calibration.status.in_(["predicted", "published"]),
            Calibration.locked_at <= cutoff,
        ).order_by(Calibration.locked_at)
    ))


def needs_rescore(session: Session) -> list[Calibration]:
    """Calibrations scored against an older rubric version (principle 2: upgrade = full re-score)."""
    current = rubric_mod.rubric_version(session)
    return list(session.scalars(
        select(Calibration).where(Calibration.rubric_version != current)
    ))


# --------------------------------------------------------------------------- rubric evolution

def evolve_rubric(session: Session, *, client=None) -> dict:
    """Aggregate reviewed calibrations and evolve the rubric. Deterministic path nudges the
    quality threshold toward the scores of works that actually over-performed (and away from
    over-scored flops). LLM path additionally refines dimension guides. Bumps the version."""
    reviewed = list(session.scalars(
        select(Calibration).where(Calibration.status == "reviewed",
                                  Calibration.calibration_error.is_not(None))
    ))
    if len(reviewed) < 3:
        raise ValueError(f"need ≥3 reviewed works to evolve rubric (have {len(reviewed)})")

    # A work "over-performed" if actual views beat prediction; "flopped" if far below.
    over = [c for c in reviewed if c.error.get("views", 0) > 20]
    flop = [c for c in reviewed if c.error.get("views", 0) < -20]
    rubric = rubric_mod.get_rubric(session)
    old_thr = float(rubric.get("threshold", 60.0))

    # If good works keep scoring low (we under-credit them) → lower the gate; if we keep passing
    # flops → raise it. Move gently toward the mean quality of the correctly-performing set.
    signal_scores = [c.quality_score for c in over] or [c.quality_score for c in reviewed]
    target = sum(signal_scores) / len(signal_scores)
    new_thr = round(old_thr + (target - old_thr) * 0.3, 1)
    new_thr = max(40.0, min(80.0, new_thr))

    dims = rubric.get("dimensions")
    note = (f"auto-evolve from {len(reviewed)} reviews "
            f"(over={len(over)}, flop={len(flop)}): threshold {old_thr}→{new_thr}")

    if client is not None:
        try:
            dims = _llm_refine_dimensions(rubric, reviewed, client) or dims
            note += " + LLM-refined dimension guides"
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM rubric refinement failed, keeping dimensions: %s", exc)

    return rubric_mod.bump_rubric(session, dimensions=dims, threshold=new_thr, note=note)


def _llm_refine_dimensions(rubric: dict, reviewed: list[Calibration], client) -> list | None:
    from app.analysis.llm import _extract_json
    sample = [{"quality": c.quality_score, "scores": c.breakdown.get("scores", {}),
               "views_error_pct": c.error.get("views")} for c in reviewed[:20]]
    system = ("你在校准短视频评分 rubric。给定历史盲评分与真实表现误差,微调各维度的评分指引"
              "(guide)使其更能预测爆款,不新增/删除维度、保持 key 与权重不变。严格输出 JSON。")
    prompt = (f"当前维度:\n{json.dumps(rubric.get('dimensions', []), ensure_ascii=False)}\n\n"
              f"历史(quality/各维度分/真实views误差%):\n{json.dumps(sample, ensure_ascii=False)}\n\n"
              f'输出: {{"dimensions": [{{"key","label","weight","guide"}}...]}}')
    data = json.loads(_extract_json(client.complete(system=system, prompt=prompt)))
    dims = data.get("dimensions")
    if not isinstance(dims, list) or not dims:
        return None
    # preserve keys+weights from the current rubric; only accept refined guides/labels
    by_key = {d["key"]: d for d in rubric.get("dimensions", [])}
    out = []
    for d in dims:
        base = by_key.get(d.get("key"))
        if base:
            out.append({**base, "label": d.get("label", base["label"]),
                        "guide": d.get("guide", base["guide"])})
    return out or None


# --------------------------------------------------------------------------- dashboard

def calibration_summary(session: Session) -> dict:
    rubric = rubric_mod.get_rubric(session)
    reviewed = list(session.scalars(
        select(Calibration).where(Calibration.status == "reviewed",
                                  Calibration.calibration_error.is_not(None))
    ))
    total = session.scalar(select(Calibration).where(Calibration.id.is_not(None)).limit(1))
    n_all = len(list(session.scalars(select(Calibration))))
    mae = round(sum(c.calibration_error for c in reviewed) / len(reviewed), 1) if reviewed else None
    passed = len(list(session.scalars(select(Calibration).where(Calibration.gate_passed.is_(True)))))
    return {
        "rubric_version": rubric.get("version", "v1"),
        "threshold": rubric.get("threshold", 60.0),
        "total": n_all,
        "reviewed": len(reviewed),
        "gate_passed": passed,
        "gate_blocked": n_all - passed,
        "mean_abs_prediction_error_pct": mae,
        "pending_review": len(pending_reviews(session)),
        "needs_rescore": len(needs_rescore(session)),
        "has_any": total is not None,
    }
