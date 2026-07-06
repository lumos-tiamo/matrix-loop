# MatrixLoop LLM 分析（Claude）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Claude 对账号做定位清晰度判定 + 内容方向分析，产出结构化 `AnalysisResult`，并把 LLM 的定位清晰度分接入评估引擎（替换 plan 2 的确定性代理分）。

**Architecture:** LLM 走可插拔接口 `LLMClient`（Protocol，方法 `complete(system, prompt) -> str`）。`analyze_positioning(account, content_items, client)` 负责构造 prompt、调用 client、抽取并校验 JSON（失败重试一次）、返回 pydantic `AnalysisResult`。真实实现 `ClaudeClient` 用 Anthropic SDK（`claude-sonnet-4-6`，读环境变量 key，可选 `base_url` 指向 OpenClaw gateway）。测试用 `FakeLLMClient`，完全不依赖真 key。`evaluate_with_analysis` 把 `AnalysisResult.positioning_clarity` 作为 positioning 子分喂给 `evaluate_account`，并同时返回 analysis（其 label / direction / suggested_topics 供后续 Loop 的起草步骤使用）。

**Tech Stack:** Python 3.13（地基同一 venv），新增依赖 `anthropic`，pydantic（已有）。

**依赖：** 地基（models）+ plan 2（`evaluate_account`、`app/analysis/content.py`）。配置前缀为 `MATRIXLOOP_`（见 `app/config.py`），故环境变量为 `MATRIXLOOP_ANTHROPIC_API_KEY`。

---

### Task 1: LLMClient 接口 + AnalysisResult 结构 + 配置/依赖

**Files:**
- Modify: `backend/requirements.txt` (追加 anthropic)
- Modify: `backend/app/config.py` (追加 3 个配置键)
- Create: `backend/app/analysis/llm.py`
- Test: `backend/tests/test_analysis_llm_schema.py`

- [ ] **Step 1: 追加依赖并安装**

Modify `backend/requirements.txt` — append one line:
```
anthropic>=0.39
```

Run: `cd backend && . .venv/bin/activate && pip install -q 'anthropic>=0.39' && python -c "import anthropic; print('ok')"`
Expected: 打印 `ok`

- [ ] **Step 2: 追加配置键**

Modify `backend/app/config.py` — add these fields inside the `Settings` class (after `database_url`):
```python
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    llm_model: str = "claude-sonnet-4-6"
```

- [ ] **Step 3: 写失败的 schema 测试**

Create `backend/tests/test_analysis_llm_schema.py`:
```python
from app.analysis.llm import AnalysisResult, LLMClient


def test_analysis_result_parses_and_defaults():
    r = AnalysisResult(
        positioning_clarity=82.5,
        positioning_label="平价美妆测评",
        content_direction="聚焦百元内产品横评",
    )
    assert r.positioning_clarity == 82.5
    assert r.positioning_label == "平价美妆测评"
    assert r.suggested_topics == []


def test_analysis_result_clamps_clarity():
    assert AnalysisResult(positioning_clarity=150, positioning_label="x", content_direction="y").positioning_clarity == 100.0
    assert AnalysisResult(positioning_clarity=-10, positioning_label="x", content_direction="y").positioning_clarity == 0.0


def test_llm_client_is_protocol_runtime_checkable():
    class Dummy:
        def complete(self, *, system: str, prompt: str) -> str:
            return "{}"
    assert isinstance(Dummy(), LLMClient)
```

- [ ] **Step 4: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_analysis_llm_schema.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.analysis.llm'`

- [ ] **Step 5: 实现 llm.py 的接口与结构**

Create `backend/app/analysis/llm.py`:
```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, *, system: str, prompt: str) -> str: ...


class AnalysisResult(BaseModel):
    positioning_clarity: float
    positioning_label: str
    content_direction: str
    suggested_topics: list[str] = Field(default_factory=list)

    @field_validator("positioning_clarity")
    @classmethod
    def _clamp_clarity(cls, v: float) -> float:
        return max(0.0, min(100.0, float(v)))
```

- [ ] **Step 6: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_analysis_llm_schema.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/requirements.txt backend/app/config.py backend/app/analysis/llm.py backend/tests/test_analysis_llm_schema.py
git commit -m "feat(analysis): LLMClient protocol + AnalysisResult schema + anthropic dep/config"
```

---

### Task 2: analyze_positioning（prompt + 解析 + 重试）

**Files:**
- Modify: `backend/app/analysis/llm.py` (追加 prompt 构造、JSON 抽取、analyze_positioning)
- Test: `backend/tests/test_analyze_positioning.py`

- [ ] **Step 1: 写失败的 analyze_positioning 测试**

Create `backend/tests/test_analyze_positioning.py`:
```python
import json

import pytest

from app.models import Account, ContentItem
from app.analysis.llm import analyze_positioning, AnalysisResult


class FakeLLMClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, *, system: str, prompt: str) -> str:
        self.calls.append({"system": system, "prompt": prompt})
        return self.responses.pop(0)


def _account():
    return Account(platform="xiaohongshu", handle="@a1", positioning="美妆")


def _content():
    return [ContentItem(account_id=1, views=100, topic="beauty"),
            ContentItem(account_id=1, views=200, topic="beauty,skincare")]


VALID = json.dumps({
    "positioning_clarity": 78,
    "positioning_label": "平价美妆测评",
    "content_direction": "聚焦百元内产品横评",
    "suggested_topics": ["5款百元粉底横评", "学生党护肤"],
})


def test_analyze_positioning_parses_valid_json():
    client = FakeLLMClient([VALID])
    result = analyze_positioning(_account(), _content(), client)
    assert isinstance(result, AnalysisResult)
    assert result.positioning_label == "平价美妆测评"
    assert result.suggested_topics == ["5款百元粉底横评", "学生党护肤"]


def test_prompt_includes_handle_and_topics():
    client = FakeLLMClient([VALID])
    analyze_positioning(_account(), _content(), client)
    prompt = client.calls[0]["prompt"]
    assert "@a1" in prompt
    assert "beauty" in prompt


def test_analyze_positioning_strips_code_fences():
    fenced = "```json\n" + VALID + "\n```"
    client = FakeLLMClient([fenced])
    result = analyze_positioning(_account(), _content(), client)
    assert result.positioning_clarity == 78.0


def test_analyze_positioning_retries_once_then_succeeds():
    client = FakeLLMClient(["not json at all", VALID])
    result = analyze_positioning(_account(), _content(), client)
    assert result.positioning_label == "平价美妆测评"
    assert len(client.calls) == 2  # retried once


def test_analyze_positioning_raises_after_two_failures():
    client = FakeLLMClient(["nope", "still nope"])
    with pytest.raises(ValueError):
        analyze_positioning(_account(), _content(), client)
    assert len(client.calls) == 2
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_analyze_positioning.py -v`
Expected: FAIL - `ImportError: cannot import name 'analyze_positioning'`

- [ ] **Step 3: 追加 analyze_positioning 到 llm.py**

Append to `backend/app/analysis/llm.py`:
```python
import json

_SYSTEM = (
    "You are a social-media account strategist. Analyze the account's positioning "
    "and content direction. Respond with ONLY a JSON object - no prose, no code fences."
)


def _build_prompt(account, content_items) -> str:
    topics = [c.topic for c in content_items if getattr(c, "topic", None)]
    return "\n".join([
        f"Platform: {account.platform}",
        f"Handle: {account.handle}",
        f"Stated positioning: {account.positioning or '(none)'}",
        f"Recent content topics: {topics if topics else '(none)'}",
        "",
        "Return a JSON object with exactly these keys:",
        '{"positioning_clarity": <number 0-100>, "positioning_label": "<short niche>", '
        '"content_direction": "<one-paragraph recommendation>", '
        '"suggested_topics": ["<topic idea>", "..."]}',
    ])


def _extract_json(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text.strip()


def analyze_positioning(account, content_items, client: LLMClient) -> AnalysisResult:
    system = _SYSTEM
    prompt = _build_prompt(account, content_items)
    last_err: Exception | None = None
    for _ in range(2):  # initial attempt + one retry
        raw = client.complete(system=system, prompt=prompt)
        try:
            return AnalysisResult(**json.loads(_extract_json(raw)))
        except Exception as err:  # noqa: BLE001 - any parse/validation error triggers retry
            last_err = err
    raise ValueError(f"LLM returned unparseable analysis after retry: {last_err}")
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_analyze_positioning.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/analysis/llm.py backend/tests/test_analyze_positioning.py
git commit -m "feat(analysis): analyze_positioning builds prompt, parses+validates JSON, retries once"
```

---

### Task 3: ClaudeClient 适配器（真实 Anthropic SDK）

**Files:**
- Create: `backend/app/analysis/claude_client.py`
- Test: `backend/tests/test_claude_client.py`

- [ ] **Step 1: 写失败的适配器测试**

Create `backend/tests/test_claude_client.py`:
```python
import sys
import types

import pytest

from app.analysis.claude_client import ClaudeClient


def test_missing_api_key_raises():
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        ClaudeClient(api_key=None)


def test_complete_builds_request_and_returns_text(monkeypatch):
    captured = {}

    class _TextBlock:
        type = "text"
        def __init__(self, text): self.text = text

    class _Message:
        content = [_TextBlock("hello world")]

    class _Messages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Message()

    class _FakeAnthropic:
        def __init__(self, **kwargs):
            captured["init"] = kwargs
            self.messages = _Messages()

    fake_module = types.SimpleNamespace(Anthropic=_FakeAnthropic)
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    client = ClaudeClient(api_key="sk-test", model="claude-sonnet-4-6")
    out = client.complete(system="SYS", prompt="PROMPT")

    assert out == "hello world"
    assert captured["model"] == "claude-sonnet-4-6"
    assert captured["system"] == "SYS"
    assert captured["messages"] == [{"role": "user", "content": "PROMPT"}]
    assert captured["init"]["api_key"] == "sk-test"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_claude_client.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.analysis.claude_client'`

- [ ] **Step 3: 实现 ClaudeClient**

Create `backend/app/analysis/claude_client.py`:
```python
from __future__ import annotations

from app.config import settings


class ClaudeClient:
    """Real LLMClient backed by the Anthropic SDK.

    Reads api key / base_url / model from Settings (env prefix MATRIXLOOP_) unless
    overridden. base_url can point at an OpenClaw gateway. Not exercised against the
    live API in tests - the request-building path is covered via a monkeypatched SDK.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = api_key if api_key is not None else settings.anthropic_api_key
        self.base_url = base_url if base_url is not None else settings.anthropic_base_url
        self.model = model or settings.llm_model
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not configured - set MATRIXLOOP_ANTHROPIC_API_KEY "
                "in the environment/.env or pass api_key=..."
            )
        import anthropic

        kwargs: dict = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = anthropic.Anthropic(**kwargs)

    def complete(self, *, system: str, prompt: str) -> str:
        message = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_claude_client.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/analysis/claude_client.py backend/tests/test_claude_client.py
git commit -m "feat(analysis): ClaudeClient adapter over Anthropic SDK (env key + optional base_url)"
```

---

### Task 4: 串联 - evaluate_with_analysis

**Files:**
- Modify: `backend/app/evaluation/scoring.py` (追加便捷函数)
- Test: `backend/tests/test_evaluate_with_analysis.py`

- [ ] **Step 1: 写失败的串联测试**

Create `backend/tests/test_evaluate_with_analysis.py`:
```python
import json
from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem
from app.evaluation.scoring import evaluate_with_analysis
from app.analysis.llm import AnalysisResult


class FakeLLMClient:
    def __init__(self, response): self.response = response
    def complete(self, *, system, prompt): return self.response


def test_evaluate_with_analysis_uses_llm_positioning():
    acc = Account(platform="x", handle="@a", objective_weights={
        "growth": 0.0, "engagement": 0.0, "commercial": 0.0, "positioning": 1.0
    })
    snaps = [Snapshot(account_id=1, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=100)]
    content = [ContentItem(account_id=1, views=100, topic="beauty")]
    client = FakeLLMClient(json.dumps({
        "positioning_clarity": 64,
        "positioning_label": "平价美妆",
        "content_direction": "聚焦横评",
        "suggested_topics": ["A", "B"],
    }))

    result, analysis = evaluate_with_analysis(acc, snaps, content, client)

    assert isinstance(analysis, AnalysisResult)
    assert analysis.positioning_label == "平价美妆"
    # weights all on positioning; positioning sub-score == LLM clarity 64
    assert result.breakdown["positioning"] == 64.0
    assert result.composite_score == 64.0
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_evaluate_with_analysis.py -v`
Expected: FAIL - `ImportError: cannot import name 'evaluate_with_analysis'`

- [ ] **Step 3: 追加 evaluate_with_analysis 到 scoring.py**

Append to `backend/app/evaluation/scoring.py`:
```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_evaluate_with_analysis.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: 跑全部测试**

Run: `cd backend && . .venv/bin/activate && python -m pytest -q`
Expected: PASS（此前 41 + 本计划 11 = 52 passed）

- [ ] **Step 6: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/evaluation/scoring.py backend/tests/test_evaluate_with_analysis.py
git commit -m "feat(evaluation): evaluate_with_analysis feeds LLM positioning clarity into scoring"
```

---

## 完成标准（本计划）

- `python -m pytest` 全绿（此前 41 + 本计划 11 = 52）
- `analyze_positioning(account, content_items, client)` 用任意 `LLMClient` 产出校验过的 `AnalysisResult`，坏 JSON 会重试一次再报错
- `ClaudeClient` 能用 `MATRIXLOOP_ANTHROPIC_API_KEY` 真连 Claude（`claude-sonnet-4-6`，可选 base_url 指 gateway），缺 key 时报清晰错误
- `evaluate_with_analysis` 用 LLM 定位清晰度替换 plan 2 的确定性代理分，并返回 analysis 供后续 Loop 起草使用
- 全程测试不依赖真 key（FakeLLMClient + monkeypatch）
