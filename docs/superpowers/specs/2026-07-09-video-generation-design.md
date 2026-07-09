# Video Generation Design (定调 → 视频, inside the loop)

**Date:** 2026-07-09
**Status:** Approved (brainstorming), pending spec review → implementation plan
**Depends on:** matrix-loop loop engine + drafts; plugs into the AiToEarn Integration spec at the "approved script → publish" seam.

## Goal

Let the user set only a channel **brief** (定调). The loop then generates short-form videos (topic → script → voiceover + visuals + captions → rendered video) for **human review**, publishes the approved video via the AiToEarn hand, and feeds real performance back to self-correct the brief. Video generation — the one genuinely costly step — is strictly **usage-governed**.

## Format decision (from deep research, 2026-07-09)

- **Main workhorse = faceless voiceover explainer:** LLM script → TTS voiceover + visuals (AI-generated clips / charts / on-chain data / B-roll) + dynamic captions.
- **Digital-human (brand avatar, e.g. Nina/Xaue) = optional low-volume variant.**

Rationale (evidence-backed): faceless has the lowest unit cost, is easiest to differentiate substantively (the key to surviving matrix anti-abuse detection), and avoids the forced AI-label + dedup-downrank risk that realistic digital humans trigger on TikTok/Meta. Digital humans are reserved for a few brand-identity accounts, not the whole matrix (API concurrency and AI-labeling do not scale to hundreds of accounts).

## Architecture principle

Consistent with the rest of matrix-loop: **brain decides, downstream executes.** Video generation sits behind a pluggable **`VideoProvider`** seam (mirrors the `LLMClient` Protocol and the connector pattern). The brain says "generate a video for this approved script under this brief"; the provider encapsulates the toolchain and returns a media artifact. The brain does not run renderers/ffmpeg itself.

**Seedance 2.0** is the first video-clip provider (interface supplied by the user later; wired behind the seam, fake-tested now — same successful pattern used for the LLM key).

## Where it plugs into the loop

```
ChannelBrief (定调)
   ↓ seeds
Loop: topic selection → script draft        (extends existing LLM draft generation)
   ↓ human approves the SCRIPT              (first + hardest cost gate)
VideoProvider.generate(script, brief)       (usage-governed; Seedance etc.)
   ↓ human approves the FINISHED VIDEO      (human-in-loop preserved)
AiToEarn publish hand  (AiToEarn Integration spec)
   ↓
real metrics ingestion → loop verify → self-correct the brief
```

## Components

### 1. `ChannelBrief` model

Fields: `account_id` (or a channel grouping id), `main_direction` (e.g. `web3`), `sub_niches` (JSON list, e.g. `["加密交易者","撸毛","空投猎人","Meme币玩家","DeFi","链上理财"]`), `tone`, `language` (e.g. `en`), `persona`, `format` (`faceless|avatar`), `compliance_stance` (default `info_education`).

The brief seeds topic/script generation (extends the existing LLM analysis / draft prompts to consume it) and is itself an object the loop self-corrects — brief tuning based on what actually performs. Existing `positioning` / `objective_weights` still apply.

### 2. Script stage (mostly exists)

The loop already produces topic + script `Draft`s via the LLM; now seeded by the `ChannelBrief`. A script `Draft` (`review_status`) is the unit a human approves **before any video spend**.

### 3. `VideoProvider` protocol (`app/video/`)

`generate(script, brief, params) -> VideoResult(media_url, duration, cost, provider, dedup_key, metadata)`.

Implementations:
- **`FacelessProvider` (default):** script → TTS (voice from a rotating pool) + visuals (Seedance clips / charts / B-roll) + captions → render → `media_url`. Sub-steps (TTS service, Seedance clip gen, render/stitch) are encapsulated inside the provider.
- **`AvatarProvider` (optional):** digital-human (e.g. HeyGen or Seedance-avatar), low volume.
- **`SeedanceClient`**: injected HTTP wrapper for Seedance 2.0 (config-gated; fake-tested now, real interface wired when provided).
- Config-gated: if no provider configured → fall back to the AiToEarn spec's "human attaches media" path.

### 4. Usage Governor (conservative defaults, all config-tunable) — `app/video/governor.py`, `VideoConfig`

The emphasized requirement. Multiple layers:

1. **Human-gate:** generation only for `adopted` script drafts — never speculative. This alone caps spend to human-approved topics.
2. **Budget circuit breaker:** `VideoConfig.video_budget` (count or credits) per batch/day; mirrors `BatchConfig.token_budget`; when cumulative usage exceeds it → hard stop (`stopped_early`).
3. **Quotas (conservative defaults):** `max_videos_per_day` global (**default 20**), `per_account_per_day` (**default 2**), `per_channel_per_day` (**default 10**). All config-tunable.
4. **Dedup:** `dedup_key = hash(script + brief + provider params)`; if an equivalent `VideoAsset` exists, reuse it instead of regenerating.
5. **Rate limit:** a semaphore honoring provider concurrency (**default 2 concurrent**) so we never blow Seedance's limits.
6. **Metering + visibility:** each `VideoAsset` records cost/credits/provider (mirrors `LoopRun.tokens_cost`); the Dashboard shows daily + cumulative video usage so spend is always visible.
7. **Pre-batch estimate:** before a batch video step, compute "N videos ≈ X cost" and require explicit confirmation above a threshold (**default: any batch that would generate > 5 videos**).

### 5. Matrix anti-abuse guardrails (from research; live in scheduler/loop) — `app/video/guardrails.py`

1. **Posting-time spread:** reject/space synchronized publishing windows (< 5 min across matrix accounts) — the strongest coordinated-inauthentic-behavior signal.
2. **TTS voice-pool rotation:** assign diverse voices per account/segment so the matrix does not collapse into a few clusterable voice fingerprints.
3. **Substantive differentiation:** per-account brief variation + a similarity check that rejects near-duplicate scripts/visuals across accounts.
4. **Compliance stance:** enforce info/education framing (not investment advice / trading promotion) to avoid crypto ad-licensing gates; surface per-platform AI-label requirements for avatar content.

### 6. `VideoAsset` model

Fields: `script_draft_id`, `account_id`, `provider`, `media_url`, `duration`, `cost`, `dedup_key`, `status` (`generating|ready|failed`), `review_status` (`pending|approved|rejected`), `created_at`.

### 7. Human-in-loop video review

A generated `VideoAsset` stays `review_status = pending`; a human reviews the **finished video**; on approval it feeds the AiToEarn publish hand (`POST /accounts/{id}/publish` with `media_urls` = the asset's `media_url`). Nothing auto-publishes.

### 8. API + batch integration

- `POST /accounts/{id}/generate-video` — gated on an adopted script draft; runs the governor + provider.
- `GET /video-assets` (filters: account, status, review_status) ; `POST /video-assets/{id}/status` (approve/reject).
- `run_batch` optional governed video step (respects budget/quotas/dedup/rate-limit).
- Config for providers + the usage caps.

## Error handling

- Per-asset isolation: a provider failure marks that `VideoAsset` `failed` and moves on; it never aborts the batch.
- Budget/quota exceeded → skip + log (a governed stop, not an error).
- Dedup hit → reuse existing asset.
- Provider unconfigured → manual-media fallback.
- Never auto-publishes; human review gate is unconditional.

## Testing

- `VideoProvider` fake (deterministic `media_url` + cost) drives all loop/API tests.
- Governor tested hermetically: budget hard-stop, per-day/per-account/per-channel quotas, dedup reuse, rate-limit semaphore.
- Anti-abuse guardrails unit-tested: time-spread rejection, voice-pool rotation assignment, near-duplicate script rejection.
- No live Seedance/TTS/render calls in the suite. Live smoke (manual) gated on the Seedance interface.

## Honest boundaries / dependencies

- Real video generation requires the Seedance 2.0 interface + credits (user-provided), plus TTS + render services (config). Conservative default caps prevent runaway spend until deliberately raised.
- Generated media must be hosted somewhere reachable by AiToEarn (upload to its S3) for the publish hand.
- Digital-human (avatar) output will be forced to carry AI labels on TikTok/Meta — by design it stays a low-volume brand variant.

## Build order (for the plan)

1. `ChannelBrief` model + seed the LLM topic/script prompts with it.
2. `VideoProvider` seam + a fake provider + `VideoAsset` model.
3. Usage Governor (budget breaker, quotas, dedup, rate-limit, metering) with conservative defaults.
4. Matrix anti-abuse guardrails.
5. Video review API + Dashboard usage panel.
6. `FacelessProvider` real toolchain + `SeedanceClient` (wired when the interface is provided).
7. Connect approved `VideoAsset` → the AiToEarn Integration publish hand.
