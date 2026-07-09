# AiToEarn Integration Design (real-data ingestion + downstream publish hand)

**Date:** 2026-07-09
**Status:** Approved (brainstorming), pending spec review → implementation plan
**Depends on:** existing matrix-loop connector layer, loop engine, scheduler

## Goal

Connect matrix-loop (the independent Python "brain") to the real world in two directions, without giving the brain any knowledge of platform internals:

1. **Ingestion (real data IN):** pull real per-account and per-post metrics so the loop evaluates on live numbers instead of demo/manual data.
2. **Publish hand (approved content OUT):** dispatch human-approved content to AiToEarn to publish/schedule.

## Architecture principle

matrix-loop stays a pure Python brain. Real-world capability is reached two ways:

- **Self-built official-API connectors** (in matrix-loop's existing connector layer): X (`twitter`, already implemented), **YouTube** (new), **Instagram** (new).
- **Delegation to a running AiToEarn service over HTTP** (`http://<host>:8080/api/v2/*`, `x-api-key`) for the anti-scraping / browser-login platforms — 小红书(`xhs`)、抖音(`douyin`)、视频号(`wxSph`)、公众号(`wxGzh`)、TikTok(`tiktok`) — and for **all publishing**.

No coupling to AiToEarn's MongoDB / Redis / BullMQ / S3 internals; only its nginx HTTP API.

**Non-goals:** rebuilding AiToEarn's internal loop engine; porting its TS/Electron connector code into Python; generating media (that is the video-generation spec's or the human's job).

## Data flow (both directions)

```
        ┌──────────────── matrix-loop brain (Python) ────────────────┐
 IN  →  │ connector registry: resolve_connector(platform)             │
 X API ─┼→ XConnector (api, exists)                                    │
 YT API ┼→ YouTubeConnector (api, new)                                 │
 IG API ┼→ InstagramConnector (api, new)         Loop engine           │
        │  AiToEarnConnector (aggregator, new) ─┐  evaluate→diagnose→   │
        │   (xhs/douyin/wxSph/wxGzh/tiktok)     │  recs→drafts→verify   │
        └───────────────────────────────────────┼──── human approves ──┘
                          GET analytics          │            │ OUT (hand)
                                                  └── AiToEarn HTTP ◄────┘
                                                      POST /channels/publish/flows
                                                            ↓
                                        小红书/抖音/视频号/公众号/TikTok real accounts
```

Closed loop: a published post's `platformWorkId` (returned by the publish flow) is stored; the next ingestion cycle pulls that work's analytics → a `ContentItem` linked to the dispatch → the loop's verify step attributes real performance to the recommendation/draft that produced it → `_mark_prev_recommendations` marks it worked/failed.

## Components

### 1. Config additions (`app/config.py`, `MATRIXLOOP_` prefix, all optional)

- `aitoearn_base_url: str | None` (e.g. `http://127.0.0.1:8080/api/v2`)
- `aitoearn_api_key: str | None`
- `youtube_api_key: str | None`
- `instagram_token: str | None`
- `instagram_business_id: str | None`

Unset values → the corresponding capability degrades gracefully (connector raises `ManualOnlyError` → CSV fallback; publish endpoint returns a clear 422 "AiToEarn 未配置").

### 2. AiToEarn HTTP client (`app/connectors/aitoearn_client.py`)

Thin wrapper. Injected `http_get`/`http_post` (mirrors `XConnector`'s injected `http_get`) so it is testable offline. `x-api-key` header from config. Methods:

- `list_accounts(types=None) -> list[dict]` → `GET /channels/accounts`
- `account_analytics(account_id, since=None, until=None) -> dict` → `GET /channels/accounts/:id/analytics`
- `work_analytics(platform, work_id, account_id, since=None, until=None) -> dict` → `GET /channels/works/:platform/:workId/analytics`
- `publish_flow(payload) -> dict` → `POST /channels/publish/flows`
- `flow_status(flow_id) -> dict` → `GET /channels/publish/flows/:flowId`

Platform-name mapping (matrix-loop ↔ AiToEarn `AccountType`): `xiaohongshu↔xhs`, `weixin_video↔wxSph`, `weixin_gzh↔wxGzh`, `douyin↔douyin`, `tiktok↔tiktok`, `twitter↔twitter`, `youtube↔youtube`, `instagram↔instagram`. matrix-loop's canonical platform strings are standardized to: `xiaohongshu`, `douyin`, `weixin_video`, `weixin_gzh`, `tiktok`, `twitter`, `youtube`, `instagram`, `bilibili`.

### 3. Ingestion connectors (`app/connectors/`)

- **`AiToEarnConnector(platform)`** — implements the `Connector` protocol. `fetch(account)`:
  - Requires `account.external_ref` (the AiToEarn accountId). If missing → raise `ManualOnlyError` (falls back to CSV).
  - `account_analytics` → one `Snapshot`: `fansCount → followers`; `engagementCount/viewCount → engagement_rate` (computed = engagement/views when both present); other metrics stored where columns exist.
  - recent works (via publish records or a works list) → `ContentItem` rows: `platformWorkId → platform_post_id`, `viewCount → views`, `likeCount → likes`, plus `comments`/`shares` (extend `ContentItem` columns if absent — verified in the plan).
  - `ConnectorResult(tier="aggregator", snapshots=..., content=...)`.
- **`YouTubeConnector`** — YouTube Data API v3. Channel `statistics.subscriberCount → followers`; recent videos `statistics.{viewCount,likeCount,commentCount} → ContentItem`. tier `"api"`. Injected `http_get`.
- **`InstagramConnector`** — Instagram Graph API (Business/Creator). Account `followers_count`; recent media insights (`impressions`/`reach`/`likes`/`comments`). tier `"api"`. Injected `http_get`.
- **Registry** (`resolve_connector`): `twitter→XConnector` (if token); `youtube→YouTubeConnector` (if key); `instagram→InstagramConnector` (if token+business id); `xiaohongshu/douyin/weixin_video/weixin_gzh/tiktok→AiToEarnConnector` (if AiToEarn configured); else `None` → `ManualOnlyError` (CSV fallback, unchanged).

### 4. Account mapping

- Add `Account.external_ref: str | None` and `Account.external_source: str | None` (e.g. `"aitoearn"`).
- `link_aitoearn_accounts(session, client) -> dict` — pulls `list_accounts`, matches AiToEarn accounts to matrix-loop accounts by (mapped platform + handle/nickname/uid), fills `external_ref`. Returns a report (linked/unmatched).
- Manual override route: `POST /accounts/{id}/external-ref` body `{external_ref, external_source}`.
- Self-built platforms (X/YT/IG) need no `external_ref` — they use `handle` + their own API tokens.

### 5. Publish hand (the downstream "hand")

- **`PublishDispatch` model:** `draft_id`, `account_id`, `aitoearn_flow_id`, `aitoearn_task_id`, `platform_work_id`, `status` (`pending|queued|published|failed`), `publish_at`, `media_urls` (JSON), `caption`, `created_at`.
- **`POST /accounts/{id}/publish`** — gated: the referenced `Draft` must be `review_status == "adopted"` (nothing speculative). Body `{draft_id, media_urls, caption, publish_at?}`. Builds the AiToEarn `publish_flow` payload (single-account item; `content.media` = `media_urls`), calls the client, records a `PublishDispatch`. **Never auto-publishes** — this endpoint is only reachable after a human approves the draft (the UI hides it behind the approved state).
- **`GET /publish/dispatches/{id}`** — polls `flow_status`, updates `platform_work_id` / `status`. Also a batch poller in the scheduler to backfill `platform_work_id` for close-the-loop.
- Media URLs must be publicly reachable by AiToEarn (or uploaded to its S3). matrix-loop does not generate media; URLs come from the video-generation spec or a human. Optional thin S3-upload proxy is a follow-up, not in scope here.

### 6. Close-the-loop wiring

Once a dispatch has a `platform_work_id`, the next ingestion cycle for that account calls `work_analytics` for it → a `ContentItem` tagged with the dispatch/draft → the loop's `_verify` / `_mark_prev_recommendations` can attribute the real delta to the recommendation and draft that produced the post.

## Error handling

- Each connector is best-effort and isolated (reuse `run_batch`'s per-account circuit breaker). AiToEarn down / unconfigured / missing `external_ref` → `ManualOnlyError` → CSV fallback; the loop still runs on existing data.
- Publish errors are surfaced (HTTP 502 + logged), the dispatch is marked `failed`; never silently swallowed.
- Auth failures (bad api-key/token) → clear 4xx from the endpoint, logged.

## Testing

- All connectors + the AiToEarn client tested with injected fake `http_get`/`http_post` (no live calls), matching AiToEarn's analytics VO shapes and publish-flow response.
- Publish endpoint: assert the built payload shape; assert the adopted-draft gate rejects non-approved drafts.
- Account linking: fake account list; assert matching + manual override.
- Hermetic; the suite never hits the network or requires a running AiToEarn.
- Live smoke (manual, out of suite): gated on a running AiToEarn stack + connected accounts.

## Honest boundaries / dependencies

- CN-platform real metrics **and all publishing** require AiToEarn running (its `docker compose`) **and** the target accounts already connected inside AiToEarn (via its Electron browser login). matrix-loop only consumes what AiToEarn already has.
- YouTube/Instagram real metrics require official API tokens (user-provided); IG requires a Business/Creator account.
- Media hosting must be reachable by AiToEarn.

## Build order (for the plan)

1. Config + AiToEarn HTTP client + platform-name mapping.
2. `AiToEarnConnector` ingestion + registry routing + `Account.external_ref` + `link_aitoearn_accounts` + manual override route.
3. YouTube + Instagram self-built connectors.
4. Publish hand: `PublishDispatch` + `POST /accounts/{id}/publish` (adopted-draft gate) + dispatch polling.
5. Close-the-loop wiring (published work → next ingestion → recommendation/draft outcome).
6. Frontend: account-link UI, publish-dispatch UI (approved draft → 发布/排期), real-data source badges.
