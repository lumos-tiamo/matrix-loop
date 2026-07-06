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
