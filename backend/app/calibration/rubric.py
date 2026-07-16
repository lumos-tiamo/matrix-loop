"""Platform-wide content rubric — the shared工作台 (not a museum) borrowed from xiaobei's
content-calibrator. One rubric for all platforms; platform differences live only in the
prediction inputs (baseline/audience/benchmark), never in the rubric itself.

The rubric is stored as JSON in AppState under RUBRIC_KEY, versioned. Evolving it bumps the
version; per xiaobei's "升级=全量重打" principle, callers should re-score the calibration pool
against the new version (surfaced via calibrations whose rubric_version != current).
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppState

logger = logging.getLogger(__name__)

RUBRIC_KEY = "calibration_rubric"

# Dimensions a work is blind-scored on (0-100 each). Weights sum to 1.0. This is the seed
# rubric; evolve_rubric mutates it from accumulated prediction error.
DEFAULT_RUBRIC: dict = {
    "version": "v1",
    "dimensions": [
        {"key": "hook", "label": "开场钩子(前3秒)", "weight": 0.30,
         "guide": "前3秒是否制造好奇/冲突/利益点,能否止住划走"},
        {"key": "value", "label": "信息价值密度", "weight": 0.25,
         "guide": "单位时长内的有效信息/洞察密度,是否言之有物"},
        {"key": "clarity", "label": "表达清晰度", "weight": 0.15,
         "guide": "结构清楚、一条主线、字幕/口播不啰嗦"},
        {"key": "differentiation", "label": "差异化", "weight": 0.15,
         "guide": "相对同题材是否有独特角度,不是套话复读"},
        {"key": "cta", "label": "行动引导/转化钩", "weight": 0.15,
         "guide": "是否自然引导关注/点击/私域,服务导流目标"},
    ],
    "threshold": 60.0,   # 质量门:低于此分不放行发布(全平台统一)
    "changelog": ["v1: seed rubric"],
}


def get_rubric(session: Session) -> dict:
    row = session.get(AppState, RUBRIC_KEY)
    if row is None or not row.value:
        return json.loads(json.dumps(DEFAULT_RUBRIC))  # deep copy
    try:
        return json.loads(row.value)
    except (ValueError, TypeError):
        logger.warning("calibration rubric in AppState is corrupt; falling back to default")
        return json.loads(json.dumps(DEFAULT_RUBRIC))


def save_rubric(session: Session, rubric: dict) -> dict:
    row = session.get(AppState, RUBRIC_KEY)
    payload = json.dumps(rubric, ensure_ascii=False)
    if row is None:
        session.add(AppState(key=RUBRIC_KEY, value=payload))
    else:
        row.value = payload
    session.commit()
    return rubric


def rubric_version(session: Session) -> str:
    return get_rubric(session).get("version", "v1")


def _next_version(version: str) -> str:
    """v1 -> v2 -> v3 ...; unknown formats get a '+' suffix so we never collide."""
    if version.startswith("v") and version[1:].isdigit():
        return f"v{int(version[1:]) + 1}"
    return f"{version}+"


def bump_rubric(session: Session, *, dimensions=None, threshold=None, note: str) -> dict:
    """Persist an evolved rubric with a bumped version + changelog entry."""
    rubric = get_rubric(session)
    new_version = _next_version(rubric.get("version", "v1"))
    if dimensions is not None:
        rubric["dimensions"] = dimensions
    if threshold is not None:
        rubric["threshold"] = float(threshold)
    rubric["version"] = new_version
    rubric.setdefault("changelog", []).append(f"{new_version}: {note}")
    return save_rubric(session, rubric)


def _sync_all_state(session: Session):
    """Test/util helper: list all AppState rows (used by tooling)."""
    return list(session.scalars(select(AppState)))
