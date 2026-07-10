# MatrixLoop — 交付说明 / Runbook

**日期:** 2026-07-09 · **状态:** 全流程打通、可交付 · **测试:** 226 后端 + 38 前端全绿

MatrixLoop 是多平台矩阵账号的**自我修正 Loop + 内容生产流水线 + 可视化指挥台**。它是一个**独立的 Python 大脑**:自己能拿的数据自己拿(官方 API),拿不到的和发布交给下游 **AiToEarn**(手),视频交给 **即梦/Seedance**。

## 全流程(已端到端验证)

```
频道定调(ChannelBrief: web3 + crypto子垂类 + 语气/英文/人设/形态)
  → Loop 选题(真 LLM) → 人审采纳选题
  → 生成脚本(真 LLM,brief 喂养) → 人审采纳脚本
  → 生成视频(VideoProvider: 真 Seedance / fake 回退,用量治理+反作弊护栏)
  → 人审成片(approve/reject)
  → 发布(AiToEarn 发布手,仅对已审通过的成片、显式触发,绝不自动发)
  → 真实数据回流 → Loop 评估「哪种选题/脚本/视频真的涨」→ 自我修正定调
```

## 已上线、经测试可用(无需外部凭证)

- **自我修正 Loop 引擎** — 目标(4权重)→采集→评估(growth/engagement/commercial/positioning)→诊断/建议/草稿→验证(回标上轮建议 worked/failed)→无进展护栏→记忆。永不自动发布。
- **真 LLM 定位分析 + 脚本生成** — Claude(key 已配 `.env`,走 newapi 中转 `claude-sonnet-4-6`)。降级:无 key 时走确定性熵代理。
- **Dashboard**(前端 :5173,深色 BI 大屏):总览/对比/爆文库/导流桑基/**视频工作台**。
- **视频生成子系统** — `ChannelBrief`、`VideoProvider` 接缝(`seedance` 真 provider + `fake` 回退)、用量治理(人审门/预算熔断/日配额 全局20·单号2·单垂类10/去重/限速/计量)、矩阵反作弊(TTS 音色池轮换 + 跨账号近重脚本拒绝)、成片人审、`/media` 静态服务。
- **数据接入(读)** — 混合连接器:X/YouTube/Instagram 自建官方 API;小红书/抖音/视频号/公众号/TikTok 走 AiToEarn;都可优雅降级到手动 CSV。
- **发布手** — `PublishDispatch` + `POST /accounts/{id}/publish`(门控:成片 approved + 账号已映射 external_ref + AiToEarn 已配)+ `GET /publish/dispatches[/{id}]`(轮询状态)。
- **批处理/调度** — `run_batch`(隔离+熔断+token/video 预算),APScheduler。

## 需要外部凭证/访问才「真联网」的(诚实边界)

| 能力 | 现状 | 打开方法 |
|---|---|---|
| **真视频画面(纯 clip)** | 三条 provider:`fake`(占位)/`seedance`(本地即梦 CLI,受账号 tier 门)/**`aitoearn`(推荐——复用 AiToEarn 视频生成,服务端持 Volcengine/Seedance/Sora 等 key,绕开即梦 tier 门)** | **推荐**:`MATRIXLOOP_VIDEO_PROVIDER=aitoearn` + `MATRIXLOOP_AITOEARN_AI_BASE_URL=http://<host>:8080/api/ai` + `MATRIXLOOP_AITOEARN_API_KEY=<key>` + `MATRIXLOOP_AITOEARN_VIDEO_MODEL=<GET /api/ai/models/video/generation 里的模型>`,`/video` 生成即出真 videoUrl。或本地 CLI:换高级即梦号 `dreamina login` + `MATRIXLOOP_VIDEO_PROVIDER=seedance` |
| **faceless 口播成片(画面+旁白+字幕)** | 第四条 provider `faceless`:AI clip 当背景 b-roll + TTS 旁白 + Pillow 烧录字幕,ffmpeg 合成竖版成片。**零 key 即可真出全长成片**(默认 macOS `say` 旁白 + ffmpeg,`test_faceless_composes_real_playable_mp4` 真跑 ffmpeg 出音+画+字幕 mp4)。注:`say` 本机不可靠(遇破折号/某些句子会截断),已加护栏——截断则回退等长静音,**保证视频永远全长+字幕计时正确**;可靠真人声请在中转开 TTS 通道走 openai 路径 | `MATRIXLOOP_VIDEO_PROVIDER=faceless` + `MATRIXLOOP_FACELESS_VISUAL=aitoearn\|seedance\|fake`(背景画面来源)+ `MATRIXLOOP_TTS_PROVIDER=auto`(默认 say,零 key)。**真人声旁白**:在中转上开一个 TTS 通道后设 `MATRIXLOOP_TTS_MODEL=<模型>`(复用 anthropic key/base;当前中转 103 模型无 TTS,需自行加通道),或 `MATRIXLOOP_TTS_BASE_URL`/`_API_KEY` 指向专用 TTS。字幕靠 ffmpeg `overlay`(本机 ffmpeg 无 libass,已改 Pillow 出 PNG 叠加,任意 ffmpeg 可跑) |
| **CN 平台真实数据 + 真发布** | 代码+门控就绪;未联网 | 跑起 AiToEarn docker + 账号在其内连接 + 设 `MATRIXLOOP_AITOEARN_BASE_URL/API_KEY` + `POST /accounts/link-aitoearn`(或手动 external_ref) |
| **X / YouTube / Instagram 真实数据** | 连接器就绪 | 设 `MATRIXLOOP_X_BEARER_TOKEN` / `MATRIXLOOP_YOUTUBE_API_KEY` / `MATRIXLOOP_INSTAGRAM_TOKEN`+`_BUSINESS_ID` |

## 本地怎么跑

```bash
# 后端(从 backend/ 启动才会加载 .env),端口 8010(:8000 被 sign-bot 生产占用)
cd ~/matrix-loop/backend
MATRIXLOOP_DATABASE_URL="sqlite:////Users/aa00102/matrix-loop/backend/data/matrixloop.db" \
  ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
# 首次/改 schema 后灌 demo:  ./.venv/bin/python seed_demo.py

# 前端,端口 5173 → 指向后端 8010
cd ~/matrix-loop/frontend
VITE_API_BASE="http://127.0.0.1:8010" npx vite --host 127.0.0.1 --port 5173
# 打开 http://127.0.0.1:5173 ；视频工作台在 /video

# 测试
cd backend && ./.venv/bin/python -m pytest -q        # 295 绿
cd frontend && npx vitest run                        # 43 绿
```

## `.env`(backend/.env,已 gitignore,勿提交)

```
MATRIXLOOP_ANTHROPIC_API_KEY=...            # 已配(newapi 中转)
MATRIXLOOP_ANTHROPIC_BASE_URL=https://newapi.elevatesphere.com
MATRIXLOOP_LLM_MODEL=claude-sonnet-4-6
# 打开真视频:
MATRIXLOOP_VIDEO_PROVIDER=seedance          # 默认 fake;可选 seedance | aitoearn | faceless
# faceless 口播成片(画面+旁白+字幕,默认 say 零 key 即可真出片):
MATRIXLOOP_VIDEO_PROVIDER=faceless
MATRIXLOOP_FACELESS_VISUAL=aitoearn         # 背景画面来源:aitoearn | seedance | fake
MATRIXLOOP_TTS_PROVIDER=auto                # auto(openai→say→fake)| say | openai | fake
MATRIXLOOP_TTS_MODEL=                        # 中转开了 TTS 通道后填模型名 → 真人声(复用 anthropic key/base)
# 打开 AiToEarn 发布/CN 数据:
MATRIXLOOP_AITOEARN_BASE_URL=http://127.0.0.1:8080/api/v2
MATRIXLOOP_AITOEARN_API_KEY=...
# 官方数据:
MATRIXLOOP_X_BEARER_TOKEN=... / MATRIXLOOP_YOUTUBE_API_KEY=... / MATRIXLOOP_INSTAGRAM_TOKEN=... MATRIXLOOP_INSTAGRAM_BUSINESS_ID=...
```

## 已知待办(follow-up,不阻塞交付)

- 视频生成目前**同步阻塞**(单条 ~≤120s);高并发前改成 submit/poll 异步 job 模型。
- Seedance `query_result` 的成片字段解析是**防御性**的(候选 key + 最新 mp4 兜底);待一个合格账号真跑一次确认确切字段(见 `app/video/seedance.py` TODO)。
- 闭环归因最后一环:用发布回传的 `platform_work_id` 拉 `work_analytics` 回写 ContentItem、归到具体建议/草稿(需逐帖采集 follow-up)。
- 发帖时间打散护栏(发布手/调度侧)。
- 前端无 ESLint(react-hooks/jsx-a11y)工具链,建议单独立。
- 真发布前把生成的媒体上传到 AiToEarn 的 S3(media_url 需 AiToEarn 可达)。

## 设计/计划文档

`docs/superpowers/specs/`(设计) 与 `docs/superpowers/plans/`(逐任务实现计划)记录了每个子系统的完整设计与 TDD 计划。
