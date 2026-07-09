# Video Generation (subsystem core) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a user-set `ChannelBrief` (定调) into human-reviewed, usage-governed short videos: brief seeds topic/script generation, an adopted script drives a pluggable `VideoProvider` (fake now, Seedance later) behind a usage governor + matrix anti-abuse guardrails, producing `VideoAsset`s that a human approves before publishing.

**Architecture:** Consistent with the codebase — brain decides, downstream executes. Video generation lives behind a `VideoProvider` Protocol (mirrors `LLMClient` in `app/analysis/llm.py` and the connector pattern). A usage governor (mirrors `BatchConfig.token_budget`) enforces a human-approval gate, dedup, per-day/per-account/per-vertical quotas, cost budget, and metering. Guardrails add TTS voice-pool rotation + near-duplicate-script rejection. Nothing auto-publishes.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, pytest. Backend Python: `backend/.venv/bin/python`; run pytest from `backend/`.

**Scope (buildable now):** `ChannelBrief`, `VideoAsset`, `VideoProvider` seam + `FakeVideoProvider` + `resolve_video_provider` factory, brief-seeded script generation, usage governor (`generate_video`), anti-abuse guardrails, batch generation + budget breaker, and the generate/review/usage APIs.

**Deferred (documented, not missing):** the real `FacelessProvider` toolchain + `SeedanceClient` (Seedance interface pending); wiring an approved `VideoAsset` into the AiToEarn publish hand (that plan not built yet); posting-time spread guardrail (belongs to the publish hand); all frontend (brief editor / video review / usage panel) — a separate plan.

Preconditions: on `main`, clean tree, `cd /Users/aa00102/matrix-loop && git checkout -b feat/video-generation`. Baseline: `cd backend && ./.venv/bin/python -m pytest -q` → 166 passed. Git identity `-c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com"`; commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

- `backend/app/models.py` (modify) — `ChannelBrief`, `VideoAsset` models.
- `backend/app/video/__init__.py` (create) — empty package marker.
- `backend/app/video/base.py` (create) — `VideoProvider` Protocol, `VideoResult`, `VideoQuotaExceeded`, `NearDuplicateScript`.
- `backend/app/video/fake.py` (create) — `FakeVideoProvider`.
- `backend/app/video/factory.py` (create) — `resolve_video_provider`.
- `backend/app/video/guardrails.py` (create) — `assign_voice`, `is_near_duplicate_script`.
- `backend/app/video/governor.py` (create) — `VideoConfig`, `generate_video`, `run_video_batch`, `estimate_batch`, `usage_summary`.
- `backend/app/analysis/script.py` (create) — `generate_script`.
- `backend/app/api/schemas.py` (modify) — `SetBrief`, `SetVideoReview` request models.
- `backend/app/api/routes.py` (modify) — brief, script-gen, generate-video, video-assets, usage routes.
- Tests: `test_models_video.py`, `test_video_provider.py`, `test_video_guardrails.py`, `test_video_governor.py`, `test_generate_script.py`, `test_api_video.py` (create).

---

### Task 1: `ChannelBrief` + `VideoAsset` models

**Files:**
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_models_video.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.models import Account, ChannelBrief, VideoAsset


def test_channel_brief_defaults_and_persist(session):
    acc = Account(platform="youtube", handle="@nina")
    session.add(acc); session.commit()
    b = ChannelBrief(account_id=acc.id, main_direction="web3",
                     sub_niches=["加密交易者", "空投猎人", "DeFi"], persona="Nina")
    session.add(b); session.commit()
    got = session.get(ChannelBrief, b.id)
    assert got.main_direction == "web3"
    assert got.sub_niches == ["加密交易者", "空投猎人", "DeFi"]
    assert got.language == "en"                 # default
    assert got.format == "faceless"             # default
    assert got.compliance_stance == "info_education"


def test_channel_brief_sub_niches_default_empty(session):
    acc = Account(platform="tiktok", handle="@z")
    session.add(acc); session.commit()
    b = ChannelBrief(account_id=acc.id, main_direction="web3")
    session.add(b); session.commit()
    assert b.sub_niches == []


def test_video_asset_defaults_and_persist(session):
    acc = Account(platform="tiktok", handle="@x")
    session.add(acc); session.commit()
    v = VideoAsset(account_id=acc.id, provider="fake", media_url="https://f/x.mp4",
                   duration=45.0, cost=1.0, dedup_key="abc")
    session.add(v); session.commit()
    got = session.get(VideoAsset, v.id)
    assert got.status == "ready"                 # default
    assert got.review_status == "pending"        # default
    assert got.cost == 1.0 and got.dedup_key == "abc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_models_video.py -q`
Expected: FAIL (`ChannelBrief` / `VideoAsset` do not exist).

- [ ] **Step 3: Add the models**

In `backend/app/models.py`, after the `AccountSegment` class (end of file), add:

```python
class ChannelBrief(Base):
    __tablename__ = "channel_briefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), unique=True, index=True)
    main_direction: Mapped[str] = mapped_column(String(128))          # e.g. web3
    sub_niches: Mapped[list] = mapped_column(JSON, default=list)      # ["加密交易者", ...]
    tone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language: Mapped[str] = mapped_column(String(16), default="en")
    persona: Mapped[str | None] = mapped_column(String(128), nullable=True)
    format: Mapped[str] = mapped_column(String(16), default="faceless")           # faceless|avatar
    compliance_stance: Mapped[str] = mapped_column(String(24), default="info_education")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def __init__(self, **kw):
        kw.setdefault("sub_niches", list())
        super().__init__(**kw)


class VideoAsset(Base):
    __tablename__ = "video_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    script_draft_id: Mapped[int | None] = mapped_column(ForeignKey("drafts.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(32))
    media_url: Mapped[str | None] = mapped_column(String, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    dedup_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="ready")              # generating|ready|failed
    review_status: Mapped[str] = mapped_column(String(16), default="pending")     # pending|approved|rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
```

(`Integer`, `String`, `Float`, `JSON`, `DateTime`, `ForeignKey`, `Mapped`, `mapped_column`, `_utcnow`, `datetime` are all already imported/defined at the top of `models.py`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_models_video.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/models.py backend/tests/test_models_video.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(models): ChannelBrief + VideoAsset\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

Note: recreate the dev DB after this plan (`rm -f backend/data/matrixloop.db && cd backend && ./.venv/bin/python seed_demo.py`). Not needed for tests (in-memory).

---

### Task 2: `VideoProvider` seam + `FakeVideoProvider` + factory

**Files:**
- Create: `backend/app/video/__init__.py` (empty), `backend/app/video/base.py`, `backend/app/video/fake.py`, `backend/app/video/factory.py`
- Test: `backend/tests/test_video_provider.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.video.base import VideoResult
from app.video.fake import FakeVideoProvider
from app.video.factory import resolve_video_provider


def test_fake_provider_is_deterministic_by_script():
    p = FakeVideoProvider()
    r1 = p.generate(script="hello world", brief=None, params={})
    r2 = p.generate(script="hello world", brief=None, params={})
    r3 = p.generate(script="different", brief=None, params={})
    assert isinstance(r1, VideoResult)
    assert r1.provider == "fake" and r1.cost > 0 and r1.duration > 0
    assert r1.media_url == r2.media_url and r1.dedup_key == r2.dedup_key
    assert r1.media_url != r3.media_url


def test_resolve_video_provider_defaults_to_fake():
    assert resolve_video_provider().name == "fake"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_video_provider.py -q`
Expected: FAIL (modules do not exist).

- [ ] **Step 3: Implement the seam**

Create `backend/app/video/__init__.py`:

```python
```

Create `backend/app/video/base.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class VideoResult:
    media_url: str
    duration: float
    cost: float
    provider: str
    dedup_key: str
    metadata: dict = field(default_factory=dict)


class VideoProvider(Protocol):
    name: str
    def generate(self, *, script: str, brief, params: dict) -> VideoResult: ...


class VideoQuotaExceeded(RuntimeError):
    """Raised when a per-day/per-account/per-vertical video quota is hit (a governed stop)."""


class NearDuplicateScript(RuntimeError):
    """Raised when a script is too similar to another account's recent script (differentiation guard)."""
```

Create `backend/app/video/fake.py`:

```python
from __future__ import annotations

import hashlib

from app.video.base import VideoResult


class FakeVideoProvider:
    """Deterministic stand-in until a real provider (Seedance) is wired. Cost is 1.0 'credit'."""

    name = "fake"

    def generate(self, *, script: str, brief, params: dict) -> VideoResult:
        digest = hashlib.sha256((script or "").encode("utf-8")).hexdigest()[:16]
        return VideoResult(
            media_url=f"https://fake.local/video/{digest}.mp4",
            duration=45.0,
            cost=1.0,
            provider=self.name,
            dedup_key=digest,
        )
```

Create `backend/app/video/factory.py`:

```python
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def resolve_video_provider():
    """Return the configured video provider. Defaults to FakeVideoProvider until a real
    provider (Seedance) is configured. Never raises — a misconfigured provider must not
    take down the loop; it falls back to fake."""
    from app.video.fake import FakeVideoProvider
    return FakeVideoProvider()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_video_provider.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/video/ backend/tests/test_video_provider.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(video): VideoProvider seam + FakeVideoProvider + factory\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: Brief-seeded script generation

**Files:**
- Create: `backend/app/analysis/script.py`
- Test: `backend/tests/test_generate_script.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.analysis.script import generate_script, build_script_prompt


class _FakeLLM:
    def __init__(self, resp): self.resp = resp; self.seen = None
    def complete(self, *, system, prompt): self.seen = prompt; return self.resp


class _Brief:
    main_direction = "web3"
    sub_niches = ["空投猎人", "DeFi"]
    tone = "punchy"
    language = "en"
    persona = "Nina"
    compliance_stance = "info_education"


def test_build_script_prompt_includes_brief_and_topic():
    p = build_script_prompt("Airdrop farming 101", _Brief())
    assert "Airdrop farming 101" in p
    assert "web3" in p and "空投猎人" in p and "Nina" in p
    assert "en" in p.lower()
    assert "info" in p.lower() and "not" in p.lower()   # compliance: info/education, not advice


def test_generate_script_returns_llm_text():
    llm = _FakeLLM("Hook: airdrops are free money if you...")
    out = generate_script("Airdrop farming 101", _Brief(), llm)
    assert out.startswith("Hook:")
    assert "Airdrop farming 101" in llm.seen        # topic was in the prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_generate_script.py -q`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Implement**

Create `backend/app/analysis/script.py`:

```python
from __future__ import annotations

_SYSTEM = (
    "You are a short-form video scriptwriter for a faceless explainer channel. "
    "Write a tight 45-60 second spoken script: a strong hook, 2-3 concrete points, "
    "and a soft call-to-follow. Output ONLY the script text, no headings or notes."
)


def build_script_prompt(topic: str, brief) -> str:
    niches = "、".join(getattr(brief, "sub_niches", None) or [])
    return "\n".join([
        f"Channel main direction: {getattr(brief, 'main_direction', '')}",
        f"Sub-niches: {niches or '(none)'}",
        f"Host persona: {getattr(brief, 'persona', None) or '(faceless voiceover)'}",
        f"Tone: {getattr(brief, 'tone', None) or 'clear and energetic'}",
        f"Language: {getattr(brief, 'language', None) or 'en'}",
        f"Topic for this video: {topic}",
        "",
        "Compliance: frame as information/education only, NOT investment advice or a "
        "trading solicitation. Avoid promises of returns.",
    ])


def generate_script(topic: str, brief, client) -> str:
    return client.complete(system=_SYSTEM, prompt=build_script_prompt(topic, brief)).strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_generate_script.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/analysis/script.py backend/tests/test_generate_script.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(analysis): brief-seeded video script generation\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: Anti-abuse guardrails

**Files:**
- Create: `backend/app/video/guardrails.py`
- Test: `backend/tests/test_video_guardrails.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.video.guardrails import assign_voice, script_similarity, is_near_duplicate_script


VOICES = ["v_alloy", "v_echo", "v_fable", "v_onyx", "v_nova"]


def test_assign_voice_deterministic_and_in_pool():
    a = assign_voice(1, VOICES)
    assert a in VOICES
    assert assign_voice(1, VOICES) == a                      # deterministic
    # different accounts spread across the pool (not all identical)
    assigned = {assign_voice(i, VOICES) for i in range(1, 20)}
    assert len(assigned) >= 3


def test_assign_voice_empty_pool_returns_default():
    assert assign_voice(1, []) == "default"


def test_script_similarity_scores_overlap():
    assert script_similarity("the quick brown fox", "the quick brown fox") == 1.0
    assert script_similarity("alpha beta gamma", "delta epsilon zeta") == 0.0
    mid = script_similarity("crypto airdrop guide today", "crypto airdrop guide tomorrow")
    assert 0.5 < mid < 1.0


def test_is_near_duplicate_flags_similar_other_account(session):
    from app.models import Account, VideoAsset, Draft, LoopRun, ChannelBrief  # noqa: F401
    a1 = Account(platform="tiktok", handle="@a1"); a2 = Account(platform="tiktok", handle="@a2")
    session.add_all([a1, a2]); session.commit()
    lr = LoopRun(account_id=a1.id); session.add(lr); session.commit()
    d = Draft(loop_run_id=lr.id, kind="script", content="crypto airdrop farming guide step by step")
    session.add(d); session.commit()
    session.add(VideoAsset(account_id=a1.id, script_draft_id=d.id, provider="fake",
                           dedup_key="k1", status="ready")); session.commit()
    # a2 attempts a near-identical script -> flagged
    assert is_near_duplicate_script(session, a2.id,
        "crypto airdrop farming guide step by step now", threshold=0.8) is True
    # a distinct script -> not flagged
    assert is_near_duplicate_script(session, a2.id,
        "defi yield strategies explained", threshold=0.8) is False
    # same account's own script does NOT count as a cross-account duplicate
    assert is_near_duplicate_script(session, a1.id,
        "crypto airdrop farming guide step by step", threshold=0.8) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_video_guardrails.py -q`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Implement**

Create `backend/app/video/guardrails.py`:

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Draft, VideoAsset


def assign_voice(account_id: int, pool: list[str]) -> str:
    """Deterministically pick a TTS voice for an account from a pool, spreading load so the
    matrix does not collapse into a few clusterable voice fingerprints."""
    if not pool:
        return "default"
    return pool[account_id % len(pool)]


def _tokens(text: str) -> set[str]:
    return {t for t in (text or "").lower().split() if t}


def script_similarity(a: str, b: str) -> float:
    """Jaccard token overlap in [0, 1]. 1.0 = identical token sets, 0.0 = disjoint."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return round(inter / union, 4) if union else 0.0


def is_near_duplicate_script(session: Session, account_id: int, script: str,
                             threshold: float = 0.85, limit: int = 200) -> bool:
    """True if `script` is >= threshold similar to a recent script used to make a VideoAsset
    on a DIFFERENT account (a matrix-differentiation guard). The account's own scripts are
    excluded (that is dedup's job, not differentiation)."""
    stmt = (
        select(Draft.content)
        .join(VideoAsset, VideoAsset.script_draft_id == Draft.id)
        .where(VideoAsset.account_id != account_id)
        .order_by(VideoAsset.id.desc())
        .limit(limit)
    )
    for (content,) in session.execute(stmt):
        if script_similarity(script, content) >= threshold:
            return True
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_video_guardrails.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/video/guardrails.py backend/tests/test_video_guardrails.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(video): anti-abuse guardrails (voice-pool rotation + near-duplicate script guard)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 5: Usage Governor — `generate_video` (human-gate, dedup, quotas, differentiation, metering)

**Files:**
- Create: `backend/app/video/governor.py`
- Test: `backend/tests/test_video_governor.py` (create)

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.models import Account, ChannelBrief, Draft, LoopRun, VideoAsset
from app.video.base import VideoQuotaExceeded, NearDuplicateScript
from app.video.fake import FakeVideoProvider
from app.video.governor import VideoConfig, generate_video


def _script_draft(session, account_id, content="crypto airdrop guide", status="adopted"):
    lr = LoopRun(account_id=account_id); session.add(lr); session.commit()
    d = Draft(loop_run_id=lr.id, kind="script", content=content, review_status=status)
    session.add(d); session.commit()
    return d


def _acct(session, handle="@x", vertical="crypto"):
    a = Account(platform="tiktok", handle=handle, vertical=vertical)
    session.add(a); session.commit()
    return a


def test_generate_requires_adopted_script(session):
    acc = _acct(session)
    d = _script_draft(session, acc.id, status="pending")
    with pytest.raises(ValueError):
        generate_video(session, acc, d, provider=FakeVideoProvider())


def test_generate_creates_ready_asset_and_meters_cost(session):
    acc = _acct(session)
    d = _script_draft(session, acc.id)
    asset = generate_video(session, acc, d, provider=FakeVideoProvider())
    assert asset.status == "ready" and asset.review_status == "pending"
    assert asset.provider == "fake" and asset.cost == 1.0 and asset.media_url
    assert asset.script_draft_id == d.id


def test_generate_dedups_identical_script(session):
    acc = _acct(session)
    d = _script_draft(session, acc.id)
    a1 = generate_video(session, acc, d, provider=FakeVideoProvider())
    a2 = generate_video(session, acc, d, provider=FakeVideoProvider())
    assert a1.id == a2.id                          # reused, not regenerated
    assert session.query(VideoAsset).count() == 1


def test_per_account_daily_quota(session):
    acc = _acct(session)
    cfg = VideoConfig(per_account_per_day=1)
    generate_video(session, acc, _script_draft(session, acc.id, "script one"), provider=FakeVideoProvider(), cfg=cfg)
    with pytest.raises(VideoQuotaExceeded):
        generate_video(session, acc, _script_draft(session, acc.id, "script two"), provider=FakeVideoProvider(), cfg=cfg)


def test_global_daily_quota(session):
    a1 = _acct(session, "@a1"); a2 = _acct(session, "@a2")
    cfg = VideoConfig(max_videos_per_day=1, per_account_per_day=5)
    generate_video(session, a1, _script_draft(session, a1.id, "one"), provider=FakeVideoProvider(), cfg=cfg)
    with pytest.raises(VideoQuotaExceeded):
        generate_video(session, a2, _script_draft(session, a2.id, "two"), provider=FakeVideoProvider(), cfg=cfg)


def test_near_duplicate_rejected(session):
    a1 = _acct(session, "@a1"); a2 = _acct(session, "@a2")
    generate_video(session, a1, _script_draft(session, a1.id, "crypto airdrop farming guide steps"),
                   provider=FakeVideoProvider())
    with pytest.raises(NearDuplicateScript):
        generate_video(session, a2, _script_draft(session, a2.id, "crypto airdrop farming guide steps"),
                       provider=FakeVideoProvider(), cfg=VideoConfig(dedup_similarity=0.8))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_video_governor.py -q`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Implement**

Create `backend/app/video/governor.py`:

```python
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, ChannelBrief, VideoAsset
from app.video.base import NearDuplicateScript, VideoQuotaExceeded
from app.video.guardrails import is_near_duplicate_script

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VideoConfig:
    max_videos_per_day: int = 20          # global across the whole matrix
    per_account_per_day: int = 2
    per_channel_per_day: int = 10         # per account.vertical (channel proxy)
    video_budget: float = 20.0            # cost/credit ceiling per batch
    max_concurrent: int = 2               # provider concurrency for batch generation
    confirm_threshold: int = 5            # batches larger than this need explicit confirmation
    dedup_similarity: float = 0.85        # cross-account near-duplicate script threshold


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)


def _count_since(session: Session, start: datetime, *, account_id: int | None = None,
                 vertical: str | None = None) -> int:
    stmt = select(func.count(VideoAsset.id)).where(VideoAsset.created_at >= start)
    if account_id is not None:
        stmt = stmt.where(VideoAsset.account_id == account_id)
    if vertical is not None:
        stmt = stmt.join(Account, Account.id == VideoAsset.account_id).where(Account.vertical == vertical)
    return int(session.scalar(stmt) or 0)


def _dedup_key(account_id: int, script: str, provider_name: str) -> str:
    raw = f"{account_id}|{script}|{provider_name}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def generate_video(session: Session, account, script_draft, *, provider,
                   brief=None, cfg: VideoConfig | None = None) -> VideoAsset:
    """Generate one governed video from an ADOPTED script draft. Layers, in order:
    human-gate -> dedup (reuse) -> cross-account differentiation -> daily quotas -> generate + meter.
    Raises ValueError (not adopted), NearDuplicateScript, or VideoQuotaExceeded to stop."""
    cfg = cfg or VideoConfig()
    if getattr(script_draft, "review_status", None) != "adopted":
        raise ValueError("script draft must be adopted before video generation (human gate)")

    script = script_draft.content or ""
    if brief is None:
        brief = session.scalar(select(ChannelBrief).where(ChannelBrief.account_id == account.id))

    # dedup: identical script for this account already produced a ready asset -> reuse
    dedup_key = _dedup_key(account.id, script, provider.name)
    existing = session.scalar(
        select(VideoAsset).where(
            VideoAsset.account_id == account.id,
            VideoAsset.dedup_key == dedup_key,
            VideoAsset.status == "ready",
        )
    )
    if existing is not None:
        return existing

    # differentiation: too similar to another account's recent script -> reject
    if is_near_duplicate_script(session, account.id, script, threshold=cfg.dedup_similarity):
        raise NearDuplicateScript(
            f"script too similar (>= {cfg.dedup_similarity}) to another account's recent video"
        )

    # daily quotas
    start = _today_start()
    if _count_since(session, start) >= cfg.max_videos_per_day:
        raise VideoQuotaExceeded(f"global daily cap {cfg.max_videos_per_day} reached")
    if _count_since(session, start, account_id=account.id) >= cfg.per_account_per_day:
        raise VideoQuotaExceeded(f"account daily cap {cfg.per_account_per_day} reached")
    if account.vertical is not None and \
            _count_since(session, start, vertical=account.vertical) >= cfg.per_channel_per_day:
        raise VideoQuotaExceeded(f"channel(vertical) daily cap {cfg.per_channel_per_day} reached")

    # generate + meter
    asset = VideoAsset(account_id=account.id, script_draft_id=script_draft.id,
                       provider=provider.name, dedup_key=dedup_key, status="generating")
    session.add(asset)
    session.flush()
    try:
        result = provider.generate(script=script, brief=brief, params={})
    except Exception as exc:  # noqa: BLE001 - isolate provider failures
        asset.status = "failed"
        session.commit()
        logger.warning("video provider %s failed for account %s: %s", provider.name, account.id, exc)
        raise
    asset.media_url = result.media_url
    asset.duration = result.duration
    asset.cost = result.cost
    asset.dedup_key = result.dedup_key or dedup_key
    asset.status = "ready"
    session.commit()
    return asset
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_video_governor.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/video/governor.py backend/tests/test_video_governor.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(video): usage governor generate_video (human-gate/dedup/quotas/differentiation/metering)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 6: Batch generation + budget breaker + estimate + usage summary

**Files:**
- Modify: `backend/app/video/governor.py`
- Test: `backend/tests/test_video_governor.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_video_governor.py`:

```python
def test_estimate_batch_counts_cost():
    from app.video.governor import estimate_batch
    est = estimate_batch(4, per_video_cost=1.0)
    assert est == {"count": 4, "estimated_cost": 4.0}


def test_run_video_batch_stops_on_budget(session):
    from app.video.governor import run_video_batch, VideoConfig
    accts = [_acct(session, f"@b{i}") for i in range(5)]
    drafts = [_script_draft(session, a.id, f"unique script number {i} about defi yields")
              for i, a in enumerate(accts)]
    pairs = list(zip(accts, drafts))
    # budget 2.0 with fake cost 1.0 each -> stops after the run that crosses the budget
    report = run_video_batch(session, pairs, provider=FakeVideoProvider(),
                             cfg=VideoConfig(video_budget=2.0, per_account_per_day=5, max_videos_per_day=99))
    assert report["stopped_early"] is True
    assert report["generated"] == 2
    assert report["total_cost"] == 2.0


def test_run_video_batch_isolates_failures(session):
    from app.video.governor import run_video_batch, VideoConfig
    a_ok = _acct(session, "@ok"); a_pending = _acct(session, "@pending")
    d_ok = _script_draft(session, a_ok.id, "airdrop hunting checklist")
    d_pending = _script_draft(session, a_pending.id, "meme coin cycle", status="pending")  # not adopted
    report = run_video_batch(session, [(a_pending, d_pending), (a_ok, d_ok)],
                             provider=FakeVideoProvider(), cfg=VideoConfig(video_budget=99))
    assert report["generated"] == 1
    assert len(report["errors"]) == 1


def test_usage_summary_reports_today_and_total(session):
    from app.video.governor import usage_summary, VideoConfig
    acc = _acct(session)
    generate_video(session, acc, _script_draft(session, acc.id, "unique defi explainer"),
                   provider=FakeVideoProvider())
    summ = usage_summary(session, cfg=VideoConfig())
    assert summ["today_count"] == 1 and summ["today_cost"] == 1.0
    assert summ["total_count"] == 1
    assert summ["caps"]["max_videos_per_day"] == 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_video_governor.py -q`
Expected: FAIL (`estimate_batch`/`run_video_batch`/`usage_summary` not defined).

- [ ] **Step 3: Implement (append to `backend/app/video/governor.py`)**

```python
def estimate_batch(count: int, per_video_cost: float = 1.0) -> dict:
    """Pre-batch estimate for the confirmation gate."""
    return {"count": count, "estimated_cost": round(count * per_video_cost, 4)}


def run_video_batch(session: Session, pairs, *, provider, cfg: VideoConfig | None = None) -> dict:
    """Generate videos for (account, script_draft) pairs under the budget breaker.
    Per-item failures (not adopted, quota, near-duplicate, provider error) are isolated.
    Stops early once cumulative cost EXCEEDS cfg.video_budget."""
    cfg = cfg or VideoConfig()
    generated = 0
    total_cost = 0.0
    errors: list[dict] = []
    stopped_early = False
    for account, draft in pairs:
        try:
            asset = generate_video(session, account, draft, provider=provider, cfg=cfg)
            generated += 1
            total_cost += asset.cost or 0.0
            if total_cost > cfg.video_budget:
                stopped_early = True
                break
        except Exception as exc:  # noqa: BLE001 - isolate per-item failures
            errors.append({"account_id": account.id, "draft_id": getattr(draft, "id", None),
                           "error": str(exc)})
    return {"generated": generated, "total_cost": round(total_cost, 4),
            "errors": errors, "stopped_early": stopped_early}


def usage_summary(session: Session, *, cfg: VideoConfig | None = None) -> dict:
    """Daily + cumulative video usage for the dashboard."""
    cfg = cfg or VideoConfig()
    start = _today_start()
    today_count = _count_since(session, start)
    today_cost = float(session.scalar(
        select(func.coalesce(func.sum(VideoAsset.cost), 0.0)).where(VideoAsset.created_at >= start)
    ) or 0.0)
    total_count = int(session.scalar(select(func.count(VideoAsset.id))) or 0)
    total_cost = float(session.scalar(select(func.coalesce(func.sum(VideoAsset.cost), 0.0))) or 0.0)
    return {
        "today_count": today_count,
        "today_cost": round(today_cost, 4),
        "total_count": total_count,
        "total_cost": round(total_cost, 4),
        "caps": {
            "max_videos_per_day": cfg.max_videos_per_day,
            "per_account_per_day": cfg.per_account_per_day,
            "per_channel_per_day": cfg.per_channel_per_day,
            "video_budget": cfg.video_budget,
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_video_governor.py -q`
Expected: PASS (6 + 4 = 10 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/video/governor.py backend/tests/test_video_governor.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(video): batch generation + budget breaker + estimate + usage summary\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 7: Brief + script-generation APIs

**Files:**
- Modify: `backend/app/api/schemas.py` (add `SetBrief`)
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_api_video.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.models import Account, ChannelBrief, Draft, LoopRun


def _seed_account(session, handle="@nina"):
    a = Account(platform="youtube", handle=handle, vertical="crypto")
    session.add(a); session.commit()
    return a


def test_upsert_and_get_brief(client, session):
    acc = _seed_account(session)
    r = client.post(f"/accounts/{acc.id}/brief", json={
        "main_direction": "web3", "sub_niches": ["空投猎人", "DeFi"], "persona": "Nina", "language": "en"})
    assert r.status_code == 200
    body = client.get(f"/accounts/{acc.id}/brief").json()
    assert body["main_direction"] == "web3" and body["sub_niches"] == ["空投猎人", "DeFi"]
    # upsert again updates in place (no duplicate row)
    client.post(f"/accounts/{acc.id}/brief", json={"main_direction": "web3", "tone": "punchy"})
    assert session.query(ChannelBrief).filter_by(account_id=acc.id).count() == 1


def test_get_brief_404_when_absent(client, session):
    acc = _seed_account(session, "@none")
    assert client.get(f"/accounts/{acc.id}/brief").status_code == 404


def test_generate_script_requires_adopted_topic(client, session, monkeypatch):
    acc = _seed_account(session)
    lr = LoopRun(account_id=acc.id); session.add(lr); session.commit()
    topic = Draft(loop_run_id=lr.id, kind="topic", content="Airdrop 101", review_status="pending")
    session.add(topic); session.commit()
    assert client.post(f"/drafts/{topic.id}/generate-script").status_code == 422  # not adopted


def test_generate_script_creates_script_draft(client, session, monkeypatch):
    acc = _seed_account(session)
    session.add(ChannelBrief(account_id=acc.id, main_direction="web3")); session.commit()
    lr = LoopRun(account_id=acc.id); session.add(lr); session.commit()
    topic = Draft(loop_run_id=lr.id, kind="topic", content="Airdrop 101", review_status="adopted")
    session.add(topic); session.commit()

    class _FakeLLM:
        def complete(self, *, system, prompt): return "Hook: airdrops explained ..."
    monkeypatch.setattr("app.api.routes.resolve_llm_client", lambda: _FakeLLM())

    r = client.post(f"/drafts/{topic.id}/generate-script")
    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == "script" and body["review_status"] == "pending"
    assert "airdrops" in body["content"].lower()


def test_generate_script_without_llm_is_422(client, session, monkeypatch):
    acc = _seed_account(session)
    lr = LoopRun(account_id=acc.id); session.add(lr); session.commit()
    topic = Draft(loop_run_id=lr.id, kind="topic", content="X", review_status="adopted")
    session.add(topic); session.commit()
    monkeypatch.setattr("app.api.routes.resolve_llm_client", lambda: None)
    assert client.post(f"/drafts/{topic.id}/generate-script").status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_api_video.py -q`
Expected: FAIL (routes missing).

- [ ] **Step 3: Add the `SetBrief` schema**

In `backend/app/api/schemas.py` add:

```python
class SetBrief(BaseModel):
    main_direction: str
    sub_niches: list[str] = []
    tone: str | None = None
    language: str = "en"
    persona: str | None = None
    format: str = "faceless"
    compliance_stance: str = "info_education"
```

- [ ] **Step 4: Add the routes**

In `backend/app/api/routes.py`, add these routes. Put `resolve_llm_client` at the top-of-file imports (it is already imported for the loop; verify — if not, add `from app.analysis.factory import resolve_llm_client`). Add `ChannelBrief`, `VideoAsset` to the existing `from app.models import ...` line.

```python
@router.post("/accounts/{account_id}/brief")
def set_brief(account_id: int, payload: schemas.SetBrief, db: Session = Depends(get_db)) -> dict:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    brief = db.scalar(select(ChannelBrief).where(ChannelBrief.account_id == account_id))
    if brief is None:
        brief = ChannelBrief(account_id=account_id, main_direction=payload.main_direction)
        db.add(brief)
    brief.main_direction = payload.main_direction
    brief.sub_niches = payload.sub_niches
    brief.tone = payload.tone
    brief.language = payload.language
    brief.persona = payload.persona
    brief.format = payload.format
    brief.compliance_stance = payload.compliance_stance
    db.commit()
    return {"account_id": account_id, "id": brief.id}


@router.get("/accounts/{account_id}/brief")
def get_brief(account_id: int, db: Session = Depends(get_db)) -> dict:
    brief = db.scalar(select(ChannelBrief).where(ChannelBrief.account_id == account_id))
    if brief is None:
        raise HTTPException(status_code=404, detail="no brief for this account")
    return {
        "account_id": account_id, "id": brief.id, "main_direction": brief.main_direction,
        "sub_niches": brief.sub_niches, "tone": brief.tone, "language": brief.language,
        "persona": brief.persona, "format": brief.format, "compliance_stance": brief.compliance_stance,
    }


@router.post("/drafts/{draft_id}/generate-script", response_model=schemas.DraftOut, status_code=201)
def generate_script_route(draft_id: int, db: Session = Depends(get_db)) -> Draft:
    topic = db.get(Draft, draft_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="draft not found")
    if topic.review_status != "adopted":
        raise HTTPException(status_code=422, detail="topic draft must be adopted first")
    client = resolve_llm_client()
    if client is None:
        raise HTTPException(status_code=422, detail="LLM 未配置(MATRIXLOOP_ANTHROPIC_API_KEY)")
    from app.analysis.script import generate_script
    lr = db.get(LoopRun, topic.loop_run_id)
    brief = db.scalar(select(ChannelBrief).where(ChannelBrief.account_id == lr.account_id))
    text = generate_script(topic.content, brief, client)
    script = Draft(loop_run_id=topic.loop_run_id, kind="script", content=text, review_status="pending")
    db.add(script)
    db.commit()
    return script
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_api_video.py -q`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/api/schemas.py backend/app/api/routes.py backend/tests/test_api_video.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(api): ChannelBrief upsert/get + generate-script (gated on adopted topic)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 8: Video generation + review + usage APIs

**Files:**
- Modify: `backend/app/api/schemas.py` (add `SetVideoReview`)
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_api_video.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_api_video.py`:

```python
def _adopted_script(session, account_id, content="unique defi yield explainer"):
    lr = LoopRun(account_id=account_id); session.add(lr); session.commit()
    d = Draft(loop_run_id=lr.id, kind="script", content=content, review_status="adopted")
    session.add(d); session.commit()
    return d


def test_generate_video_gated_on_adopted_script(client, session):
    acc = _seed_account(session)
    lr = LoopRun(account_id=acc.id); session.add(lr); session.commit()
    d = Draft(loop_run_id=lr.id, kind="script", content="x", review_status="pending")
    session.add(d); session.commit()
    r = client.post(f"/accounts/{acc.id}/generate-video", json={"script_draft_id": d.id})
    assert r.status_code == 422


def test_generate_video_creates_asset(client, session):
    acc = _seed_account(session)
    d = _adopted_script(session, acc.id)
    r = client.post(f"/accounts/{acc.id}/generate-video", json={"script_draft_id": d.id})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "ready" and body["review_status"] == "pending" and body["provider"] == "fake"


def test_list_and_review_video_assets(client, session):
    acc = _seed_account(session)
    d = _adopted_script(session, acc.id)
    vid = client.post(f"/accounts/{acc.id}/generate-video", json={"script_draft_id": d.id}).json()
    listing = client.get(f"/video-assets?account_id={acc.id}").json()
    assert any(v["id"] == vid["id"] for v in listing)
    r = client.post(f"/video-assets/{vid['id']}/status", json={"review_status": "approved"})
    assert r.status_code == 200 and r.json()["review_status"] == "approved"
    assert client.post(f"/video-assets/{vid['id']}/status", json={"review_status": "bogus"}).status_code == 422


def test_video_usage_endpoint(client, session):
    acc = _seed_account(session)
    client.post(f"/accounts/{acc.id}/generate-video",
                json={"script_draft_id": _adopted_script(session, acc.id).id})
    usage = client.get("/video/usage").json()
    assert usage["today_count"] >= 1 and usage["caps"]["per_account_per_day"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_api_video.py -q`
Expected: FAIL (routes missing).

- [ ] **Step 3: Add the `SetVideoReview` schema**

In `backend/app/api/schemas.py` add:

```python
class SetVideoReview(BaseModel):
    review_status: str
```

- [ ] **Step 4: Add the routes**

In `backend/app/api/routes.py`, add. Import at top: `from app.video.factory import resolve_video_provider`, `from app.video.governor import generate_video, usage_summary, VideoConfig`, `from app.video.base import VideoQuotaExceeded, NearDuplicateScript`. Ensure `VideoAsset` is in the `from app.models import ...` line.

```python
_VIDEO_REVIEW_STATUSES = {"pending", "approved", "rejected"}


@router.post("/accounts/{account_id}/generate-video", response_model=schemas.VideoAssetOut, status_code=201)
def generate_video_route(account_id: int, payload: schemas.GenerateVideoIn, db: Session = Depends(get_db)) -> VideoAsset:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    draft = db.get(Draft, payload.script_draft_id)
    if draft is None or draft.kind != "script":
        raise HTTPException(status_code=404, detail="script draft not found")
    try:
        return generate_video(db, acc, draft, provider=resolve_video_provider())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NearDuplicateScript as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except VideoQuotaExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


@router.get("/video-assets", response_model=list[schemas.VideoAssetOut])
def list_video_assets(account_id: int | None = None, status: str | None = None,
                      review_status: str | None = None, db: Session = Depends(get_db)) -> list[VideoAsset]:
    stmt = select(VideoAsset).order_by(VideoAsset.id.desc())
    if account_id is not None:
        stmt = stmt.where(VideoAsset.account_id == account_id)
    if status is not None:
        stmt = stmt.where(VideoAsset.status == status)
    if review_status is not None:
        stmt = stmt.where(VideoAsset.review_status == review_status)
    return list(db.scalars(stmt).all())


@router.post("/video-assets/{asset_id}/status", response_model=schemas.VideoAssetOut)
def set_video_review(asset_id: int, payload: schemas.SetVideoReview, db: Session = Depends(get_db)) -> VideoAsset:
    asset = db.get(VideoAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="video asset not found")
    if payload.review_status not in _VIDEO_REVIEW_STATUSES:
        raise HTTPException(status_code=422, detail=f"invalid review_status; allowed: {sorted(_VIDEO_REVIEW_STATUSES)}")
    asset.review_status = payload.review_status
    db.commit()
    return asset


@router.get("/video/usage")
def video_usage(db: Session = Depends(get_db)) -> dict:
    return usage_summary(db, cfg=VideoConfig())
```

- [ ] **Step 5: Add the `GenerateVideoIn` + `VideoAssetOut` schemas**

In `backend/app/api/schemas.py` add (near the other request/response models; `datetime`, `ConfigDict`, `BaseModel` are already imported there):

```python
class GenerateVideoIn(BaseModel):
    script_draft_id: int


class VideoAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    script_draft_id: int | None
    provider: str
    media_url: str | None
    duration: float | None
    cost: float
    status: str
    review_status: str
    created_at: datetime
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_api_video.py -q`
Expected: PASS (5 + 4 = 9 tests).

- [ ] **Step 7: Full suite regression**

Run: `cd backend && ./.venv/bin/python -m pytest -q`
Expected: all pass (166 baseline + all new tests from Tasks 1-8).

- [ ] **Step 8: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/api/schemas.py backend/app/api/routes.py backend/tests/test_api_video.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(api): generate-video (governed) + video-assets list/review + /video/usage\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## After all tasks

- Dispatch a final code review over the branch diff (`git diff main..HEAD`).
- Recreate the dev DB for the new tables: `rm -f backend/data/matrixloop.db && cd backend && ./.venv/bin/python seed_demo.py`.
- Use `superpowers:finishing-a-development-branch` to merge to `main` (option 1, `--no-ff`).

## Deferred follow-ups (documented, not in this plan)

- Real `FacelessProvider` toolchain + `SeedanceClient` behind the same `VideoProvider` seam (wired when the Seedance 2.0 interface is provided; `resolve_video_provider` swaps the default).
- Wiring an approved `VideoAsset` → the AiToEarn publish hand (that plan is not built yet).
- Posting-time spread guardrail (belongs with the publish hand / scheduler).
- Frontend: ChannelBrief editor, video review queue, usage panel on the dashboard.
- Assigning the guardrail voice (`assign_voice`) into real provider params once the faceless toolchain exists.

## Self-review notes (against the spec)

- **Spec coverage:** ChannelBrief (Task 1) + brief-seeded scripts (Tasks 3, 7); VideoProvider seam + fake + factory (Task 2); VideoAsset (Task 1); usage governor with human-gate/dedup/quotas/metering (Task 5) + budget breaker + estimate + usage (Task 6); anti-abuse voice-pool + near-duplicate (Task 4, wired in Task 5); generate/review/usage APIs (Tasks 7-8). Deferred items match the spec's build-order tail and are documented above.
- **Type consistency:** `VideoResult`/`VideoProvider` used uniformly; `generate_video(session, account, script_draft, *, provider, brief=None, cfg=None)` signature matches all call sites (governor tests, batch, API); `VideoConfig` field names match the usage_summary caps + tests; `VideoAsset` columns match `VideoAssetOut`; raise types (`ValueError`/`NearDuplicateScript`/`VideoQuotaExceeded`) map to 422/409/429 in the API.
- **No placeholders:** every step has full code, exact commands, expected outcomes.
