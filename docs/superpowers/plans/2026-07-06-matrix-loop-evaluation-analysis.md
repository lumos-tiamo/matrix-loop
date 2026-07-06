# MatrixLoop 评估引擎 + 确定性分析 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在地基之上，实现单账号价值评估（四目标加权复合分 0-100）与确定性内容分析（爆文拆解 + 定位分散度代理），全程不依赖 LLM、可确定性测试。

**Architecture:** 两个纯函数模块。`app/evaluation/scoring.py` 从快照指标算 growth/engagement/commercial 子分，按 `account.objective_weights` 加权成复合分，`positioning` 子分作为入参传入。`app/analysis/content.py` 从内容项算爆文集合、内容标签香农熵（归一化 0-1）、以及定位清晰度代理分 `(1 - 熵) * 100`。一个便捷函数 `evaluate_with_content` 用代理分喂给评估引擎，把两者串起来。LLM 版定位判定在 plan 3 增强。

**Tech Stack:** Python 3.13（地基用的同一 venv），pytest。无新依赖。

**依赖：** 地基（models `Account`/`Snapshot`/`ContentItem`，其 `__init__` 已保证 `objective_weights`/`topic` 等可在未 flush 时读取）。用真实模型对象（无需入库）构造测试输入。

**评分口径（默认，可调）：** 每个原始指标按一个「目标参考值」线性映射到 0-100 并裁剪；复合分 = 各子分按账号权重归一加权。定位清晰度 = 内容标签越集中分越高。

---

### Task 1: 评估评分引擎

**Files:**
- Create: `backend/app/evaluation/__init__.py`
- Create: `backend/app/evaluation/scoring.py`
- Test: `backend/tests/test_evaluation_scoring.py`

- [ ] **Step 1: 写失败的评分测试**

Create `backend/tests/test_evaluation_scoring.py`:
```python
from datetime import datetime, timezone

from app.models import Account, Snapshot
from app.evaluation.scoring import (
    ScoringConfig,
    growth_score,
    engagement_score,
    commercial_score,
    evaluate_account,
)


def _snap(ts_day, followers=None, engagement_rate=None, conversions=None):
    return Snapshot(
        account_id=1,
        ts=datetime(2026, 7, ts_day, tzinfo=timezone.utc),
        followers=followers,
        engagement_rate=engagement_rate,
        conversions=conversions,
    )


def test_growth_score_hits_100_at_target():
    cfg = ScoringConfig(target_growth_rate=0.10)
    snaps = [_snap(1, followers=100000), _snap(6, followers=110000)]  # +10%
    assert growth_score(snaps, cfg) == 100.0


def test_growth_score_zero_with_single_snapshot():
    assert growth_score([_snap(1, followers=100000)], ScoringConfig()) == 0.0


def test_engagement_score_scales_and_clamps():
    cfg = ScoringConfig(target_engagement_rate=0.05)
    assert engagement_score(_snap(6, engagement_rate=0.025), cfg) == 50.0
    assert engagement_score(_snap(6, engagement_rate=0.20), cfg) == 100.0  # clamped


def test_commercial_score():
    cfg = ScoringConfig(target_conversions=10)
    assert commercial_score(_snap(6, conversions=5), cfg) == 50.0


def test_evaluate_account_weighted_composite():
    acc = Account(platform="x", handle="@a", objective_weights={
        "growth": 0.4, "engagement": 0.3, "commercial": 0.2, "positioning": 0.1
    })
    snaps = [_snap(1, followers=100000, engagement_rate=0.05, conversions=10),
             _snap(6, followers=110000, engagement_rate=0.05, conversions=10)]
    result = evaluate_account(acc, snaps, positioning_score=80.0)
    # growth=100, engagement=100, commercial=100, positioning=80
    # composite = 0.4*100 + 0.3*100 + 0.2*100 + 0.1*80 = 98.0
    assert result.breakdown == {"growth": 100.0, "engagement": 100.0, "commercial": 100.0, "positioning": 80.0}
    assert result.composite_score == 98.0
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_evaluation_scoring.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.evaluation'`

- [ ] **Step 3: 实现评分引擎**

Create `backend/app/evaluation/__init__.py` (空文件).

Create `backend/app/evaluation/scoring.py`:
```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringConfig:
    target_growth_rate: float = 0.10       # 期望评估窗口内涨粉比例
    target_engagement_rate: float = 0.05   # 期望互动率
    target_conversions: int = 10           # 期望转化/线索数


@dataclass
class EvaluationResult:
    composite_score: float
    breakdown: dict


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def growth_score(snapshots, cfg: ScoringConfig) -> float:
    snaps = sorted((s for s in snapshots if s.followers is not None), key=lambda s: s.ts)
    if len(snaps) < 2 or not snaps[0].followers:
        return 0.0
    rate = (snaps[-1].followers - snaps[0].followers) / snaps[0].followers
    return round(_clamp(rate / cfg.target_growth_rate * 100), 2)


def engagement_score(latest, cfg: ScoringConfig) -> float:
    er = getattr(latest, "engagement_rate", None) or 0.0
    return round(_clamp(er / cfg.target_engagement_rate * 100), 2)


def commercial_score(latest, cfg: ScoringConfig) -> float:
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
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_evaluation_scoring.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/evaluation backend/tests/test_evaluation_scoring.py
git commit -m "feat(evaluation): weighted composite value score from snapshot metrics"
```

---

### Task 2: 确定性内容分析（爆文 + 定位分散度）

**Files:**
- Create: `backend/app/analysis/__init__.py`
- Create: `backend/app/analysis/content.py`
- Test: `backend/tests/test_analysis_content.py`

- [ ] **Step 1: 写失败的分析测试**

Create `backend/tests/test_analysis_content.py`:
```python
from app.models import ContentItem
from app.analysis.content import hit_content, tag_entropy, positioning_proxy_score


def _ci(views, topic=None):
    return ContentItem(account_id=1, views=views, topic=topic)


def test_hit_content_picks_outliers():
    items = [_ci(100), _ci(120), _ci(90), _ci(1000)]  # median ~110, 3x=330
    hits = hit_content(items, multiplier=3.0)
    assert [c.views for c in hits] == [1000]


def test_hit_content_empty():
    assert hit_content([], multiplier=3.0) == []


def test_tag_entropy_single_tag_is_zero():
    items = [_ci(100, "beauty"), _ci(100, "beauty"), _ci(100, "beauty")]
    assert tag_entropy(items) == 0.0


def test_tag_entropy_uniform_is_one():
    items = [_ci(100, "beauty"), _ci(100, "fashion"), _ci(100, "travel"), _ci(100, "food")]
    assert tag_entropy(items) == 1.0


def test_tag_entropy_no_tags_is_zero():
    assert tag_entropy([_ci(100), _ci(100)]) == 0.0


def test_positioning_proxy_focused_is_high():
    focused = [_ci(100, "beauty")] * 4
    scattered = [_ci(100, "beauty"), _ci(100, "fashion"), _ci(100, "travel"), _ci(100, "food")]
    assert positioning_proxy_score(focused) == 100.0
    assert positioning_proxy_score(scattered) == 0.0
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_analysis_content.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.analysis'`

- [ ] **Step 3: 实现内容分析**

Create `backend/app/analysis/__init__.py` (空文件).

Create `backend/app/analysis/content.py`:
```python
from __future__ import annotations

import math
from collections import Counter


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def hit_content(content_items, multiplier: float = 3.0) -> list:
    """爆文：views >= multiplier * 中位数 views。空输入或中位数<=0 返回空。"""
    views = [c.views or 0 for c in content_items]
    median = _median(views)
    if median <= 0:
        return []
    threshold = multiplier * median
    return [c for c in content_items if (c.views or 0) >= threshold]


def _tags(content_items) -> list[str]:
    tags: list[str] = []
    for c in content_items:
        if c.topic:
            tags.extend(t.strip() for t in c.topic.split(",") if t.strip())
    return tags


def tag_entropy(content_items) -> float:
    """内容标签的归一化香农熵 (0-1)。0=完全聚焦，1=完全发散。"""
    tags = _tags(content_items)
    if not tags:
        return 0.0
    counts = Counter(tags)
    if len(counts) <= 1:
        return 0.0
    total = len(tags)
    entropy = -sum((n / total) * math.log2(n / total) for n in counts.values())
    return round(entropy / math.log2(len(counts)), 6)


def positioning_proxy_score(content_items) -> float:
    """确定性定位清晰度代理分：(1 - 归一化熵) * 100。LLM 判定在 plan 3 增强/替换。"""
    return round((1.0 - tag_entropy(content_items)) * 100, 2)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_analysis_content.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/analysis backend/tests/test_analysis_content.py
git commit -m "feat(analysis): deterministic content breakdown (hit posts) + positioning dispersion proxy"
```

---

### Task 3: 串联 - evaluate_with_content

**Files:**
- Modify: `backend/app/evaluation/scoring.py` (追加便捷函数)
- Test: `backend/tests/test_evaluate_with_content.py`

- [ ] **Step 1: 写失败的串联测试**

Create `backend/tests/test_evaluate_with_content.py`:
```python
from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem
from app.evaluation.scoring import evaluate_with_content


def test_evaluate_with_content_uses_positioning_proxy():
    acc = Account(platform="xiaohongshu", handle="@a", objective_weights={
        "growth": 0.0, "engagement": 0.0, "commercial": 0.0, "positioning": 1.0
    })
    snaps = [
        Snapshot(account_id=1, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100),
        Snapshot(account_id=1, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110),
    ]
    focused = [ContentItem(account_id=1, views=100, topic="beauty")] * 4
    result = evaluate_with_content(acc, snaps, focused)
    # 权重全压 positioning，focused 内容 → positioning=100 → composite=100
    assert result.breakdown["positioning"] == 100.0
    assert result.composite_score == 100.0
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_evaluate_with_content.py -v`
Expected: FAIL - `ImportError: cannot import name 'evaluate_with_content'`

- [ ] **Step 3: 追加便捷函数**

Append to `backend/app/evaluation/scoring.py`:
```python
def evaluate_with_content(account, snapshots, content_items, cfg: ScoringConfig | None = None) -> EvaluationResult:
    """便捷入口：用确定性内容分析的定位代理分，喂给 evaluate_account。

    plan 3 将用 LLM 定位清晰度替换/增强这里的 positioning_score。
    """
    from app.analysis.content import positioning_proxy_score

    positioning = positioning_proxy_score(content_items)
    return evaluate_account(account, snapshots, positioning_score=positioning, cfg=cfg)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_evaluate_with_content.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: 跑全部测试**

Run: `cd backend && . .venv/bin/activate && python -m pytest -q`
Expected: PASS（地基 18 + 本计划 12 = 30 passed）

- [ ] **Step 6: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/evaluation/scoring.py backend/tests/test_evaluate_with_content.py
git commit -m "feat(evaluation): evaluate_with_content ties positioning proxy into scoring"
```

---

## 完成标准（本计划）

- `python -m pytest` 全绿（含地基共 30 用例）
- `evaluate_account(account, snapshots, positioning_score)` 产出 0-100 复合分 + 四项拆解
- `evaluate_with_content(account, snapshots, content_items)` 用确定性定位代理分自动串起来
- 均为纯确定性、无 LLM 依赖；plan 3（LLM 分析）将用真实定位判定替换 positioning 代理分
