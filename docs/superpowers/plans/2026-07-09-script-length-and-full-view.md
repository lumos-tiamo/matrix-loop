# Configurable Script Length + Full-Script View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** (1) Make video-script length part of the channel 定调 — a per-`ChannelBrief` `target_seconds` that drives the script generator's length; (2) let the `/video` workbench show the FULL script (expandable), not a 200-char preview.

**Architecture:** Backend adds `ChannelBrief.target_seconds` (default 50) surfaced via the brief API and consumed by `build_script_prompt` (the length guidance becomes dynamic; the system prompt stops hardcoding "45-60s"). Frontend adds a "视频时长(秒)" field to the brief editor and makes each draft card expandable to full content.

**Tech Stack:** backend Python (FastAPI/SQLAlchemy, pytest); frontend Vite/React/TS (vitest). Backend Python: `backend/.venv/bin/python` from `backend/`; frontend from `frontend/`.

Preconditions: on `main`, clean, `git checkout -b feat/script-length`. Baseline: backend 262 tests, frontend 41 tests green. Git identity `-c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com"`; commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: `ChannelBrief.target_seconds` + API + prompt wiring (backend)

**Files:** `backend/app/models.py`, `backend/app/api/schemas.py`, `backend/app/api/routes.py`, `backend/app/analysis/script.py`; Test `backend/tests/test_generate_script.py` (extend), `backend/tests/test_api_video.py` (extend).

- [ ] **Step 1: Write the failing tests**

Extend `backend/tests/test_generate_script.py`:

```python
def test_build_script_prompt_uses_target_seconds():
    from app.analysis.script import build_script_prompt
    class B:
        main_direction="web3"; sub_niches=["defi"]; tone="punchy"; language="en"
        persona="Nina"; compliance_stance="info_education"; target_seconds=90
    p = build_script_prompt("Topic", B())
    assert "90" in p                      # target seconds surfaced
    # word budget roughly target_seconds * ~2.7
    assert "word" in p.lower()


def test_build_script_prompt_defaults_when_no_target():
    from app.analysis.script import build_script_prompt
    class B:
        main_direction="web3"; sub_niches=[]; tone=None; language="en"; persona=None; compliance_stance="info_education"
    p = build_script_prompt("Topic", B())   # no target_seconds attr -> default 50
    assert "50" in p
```

Extend `backend/tests/test_api_video.py`:

```python
def test_brief_roundtrips_target_seconds(client, session):
    acc = _seed_account(session)
    client.post(f"/accounts/{acc.id}/brief", json={"main_direction": "web3", "target_seconds": 90})
    body = client.get(f"/accounts/{acc.id}/brief").json()
    assert body["target_seconds"] == 90
```

(`_seed_account` already exists in `test_api_video.py`.)

- [ ] **Step 2: Run — expect FAIL.** `cd backend && ./.venv/bin/python -m pytest tests/test_generate_script.py tests/test_api_video.py -q`

- [ ] **Step 3: Model** — in `backend/app/models.py` `class ChannelBrief`, after `format`, add:

```python
    target_seconds: Mapped[int] = mapped_column(default=50, server_default="50", nullable=False)
```

- [ ] **Step 4: Schema** — in `backend/app/api/schemas.py` `class SetBrief`, add `target_seconds: int = 50`.

- [ ] **Step 5: Routes** — in `backend/app/api/routes.py`:
  - `set_brief`: add `brief.target_seconds = payload.target_seconds` alongside the other field assignments.
  - `get_brief`: add `"target_seconds": brief.target_seconds` to the returned dict.

- [ ] **Step 6: Prompt wiring** — in `backend/app/analysis/script.py`:
  - Change `_SYSTEM` to not hardcode duration:
    ```python
    _SYSTEM = (
        "You are a short-form video scriptwriter for a faceless explainer channel. "
        "Write a tight spoken script with a strong hook, concrete points, and a soft "
        "call-to-follow. Target length is specified in the prompt. Output ONLY the script "
        "text, no headings or notes."
    )
    ```
  - In `build_script_prompt(topic, brief, performance=None, trends=None)`, compute the target and add a length line to the prompt body (before the compliance line):
    ```python
        secs = int(getattr(brief, "target_seconds", None) or 50)
        words = round(secs * 2.7)
        # ... in the lines list, add:
        f"Target length: a ~{secs}-second spoken script (~{words} words). Do not pad; match this length.",
    ```
    (Place the `Target length:` line right after the `Topic for this video:` line.)

- [ ] **Step 7: Run — expect PASS** (`test_generate_script.py test_api_video.py`). Confirm existing script/brief tests still pass (target defaults to 50; the new line is additive).

- [ ] **Step 8: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/models.py backend/app/api/schemas.py backend/app/api/routes.py backend/app/analysis/script.py backend/tests/test_generate_script.py backend/tests/test_api_video.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(loop): per-brief target_seconds drives script length\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

Note: recreate dev DB after this plan (new column).

---

### Task 2: Brief editor length field + expandable full script (frontend)

**Files:** `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/pages/Video.tsx`; Test `frontend/src/pages/Video.test.tsx` (extend).

- [ ] **Step 1: Types + client** — in `frontend/src/api/types.ts`:
  - `ChannelBriefOut`: add `target_seconds: number;`
  - `SetBriefIn`: add `target_seconds?: number;`

  No client method change needed (setBrief passes the body through; ensure the Video page includes `target_seconds` in the body).

- [ ] **Step 2: Write the failing test** — extend `frontend/src/pages/Video.test.tsx`. Add a test that the brief editor renders a length field pre-filled from the loaded brief, and a test that a draft card can expand to show full content. (Follow the existing stub-fetch pattern in that file; the brief stub must include `target_seconds`.)

```tsx
it("brief editor shows the target-seconds field from the loaded brief", async () => {
  // stub /accounts -> [acct4], /video/usage, /accounts/4/brief -> {..., target_seconds: 90}, /accounts/4 -> detail
  // render <Flywheel? no -> the Video page>, select account 4, assert an input with value "90" exists (aria-label 视频时长)
});

it("a topic/script draft card expands to show full content", async () => {
  // detail with a script draft whose content is a long (>200 char) string
  // render Video, select account, assert the preview is shown; click 展开全文; assert the full (>200) text is now present
});
```

Write these fully against the real component per the existing test conventions in `Video.test.tsx` (there are already brief + draft tests to mirror). Use `aria-label="视频时长"` on the new input so the test can target it.

- [ ] **Step 3: Run — expect FAIL.** `cd frontend && npx vitest run src/pages/Video.test.tsx`

- [ ] **Step 4: Implement in `frontend/src/pages/Video.tsx`**

  **BriefEditor:** add `target_seconds` to the editor state (default 50), hydrate from the loaded brief (`b?.target_seconds ?? 50`), add an input:
  ```tsx
  <input aria-label="视频时长" type="number" min={15} max={180} className={inputCls}
    placeholder="视频时长(秒)" value={targetSeconds}
    onChange={(e) => setTargetSeconds(Number(e.target.value) || 50)} />
  ```
  and include `target_seconds: targetSeconds` in the `api.setBrief(...)` body.

  **DraftWorkflow:** replace `d.content.slice(0, 200)` with an expandable block. Add per-draft expand state (`const [expanded, setExpanded] = useState<Set<number>>(new Set())`) and render:
  ```tsx
  <p className="mb-2 whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-text">
    {expanded.has(d.id) ? d.content : d.content.slice(0, 200)}
    {d.content.length > 200 && (
      <button className="ml-1 text-cyan hover:underline"
        onClick={() => setExpanded((s) => { const n = new Set(s); n.has(d.id) ? n.delete(d.id) : n.add(d.id); return n; })}>
        {expanded.has(d.id) ? " 收起" : " …展开全文"}
      </button>
    )}
  </p>
  ```
  (`whitespace-pre-wrap` preserves script line breaks.)

- [ ] **Step 5: Run — expect PASS.** `npx vitest run src/pages/Video.test.tsx`

- [ ] **Step 6: Typecheck + full suite** — `npx tsc --noEmit && npx vitest run` — clean, all pass.

- [ ] **Step 7: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/pages/Video.tsx frontend/src/pages/Video.test.tsx
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(fe): brief target-seconds field + expandable full script in workbench\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## After all tasks

- Recreate dev DB (`rm -f backend/data/matrixloop.db && cd backend && ./.venv/bin/python seed_demo.py`).
- Final review over the branch; `superpowers:finishing-a-development-branch` → merge `main` (`--no-ff`).
- Optional: raise the demo script preview from `[:200]` to `[:400]` (cosmetic).

## Self-review

- Coverage: per-brief `target_seconds` (T1: model+schema+routes+prompt), editor field + expandable draft (T2). Optional params keep existing callers working.
- Type consistency: `build_script_prompt(topic, brief, performance=None, trends=None)` unchanged signature (reads `brief.target_seconds` via getattr default 50); `ChannelBriefOut.target_seconds`/`SetBriefIn.target_seconds` match backend.
- No placeholders: full code + commands (frontend test bodies to be written against the existing Video.test.tsx conventions).
