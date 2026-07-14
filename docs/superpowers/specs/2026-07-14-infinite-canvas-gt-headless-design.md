# Infinite-Canvas-GT → 无头内容生成服务（并入 matrix-loop 生态）

**日期**: 2026-07-14
**分支**: `feat/infinite-canvas-gt-headless`
**位置**: `~/matrix-loop/infinite-canvas-gt/`
**状态**: 设计已确认（用户："设计OK 我只看结果"），进入实现

## 目标

把第三方项目 Infinite-Canvas-GT 从"手动点界面"改造成一个**无头生成服务**，让 matrix-loop 的内容 loop 用代码批量调它出图/出视频。两块：
1. **安全加固**——让 loop 能安全调用的前提（服务当前 0 鉴权 + 监听 0.0.0.0 + 明文吐密钥 + 无鉴权自更新端点）。
2. **统一「内容作业」API**——在项目上新增一层 `/api/jobs`，把各家 provider 差异藏在后面，loop 只对接一个稳定契约。

## 关键决策（brainstorm 结论）

| 维度 | 决定 |
|---|---|
| 意图 | 项目改造成无头 API，接入内容 loop |
| 接口契约 | 新增统一「内容作业」API（submit → poll → artifacts） |
| 产出类型 | 文生图 / 图生图 / 文生视频 / 图生视频（全覆盖） |
| 引擎路由 | ModelScope（免费图）/ 即梦 CLI（视频主力）/ RunningHub / 火山·OpenAI兼容·本地ComfyUI（全覆盖，可配置默认+降级） |
| 部署 | 同机共存：监听 127.0.0.1，回环免 token，产物回本地绝对路径 |

## 架构

```
matrix-loop  --POST /api/jobs-->  Infinite-Canvas-GT (127.0.0.1:3000)
             <--GET /api/jobs/{id}--   jobs/ 包 (自包含，不改上帝文件)
                                       └ worker 用 localhost httpx 复用现有 139 端点
                                       产物 → assets/output/*.png|.mp4 (本地绝对路径回传)
```

**核心原则**: 不重写 provider 逻辑、不喂胖 15011 行的 `main.py`。作业层是独立 `jobs/` 包，`main.py` 只加 `include_router` + startup 拉起 worker。adapter 通过回环 HTTP 复用现有端点，与内部函数零耦合。

## 统一作业 API 契约

- `POST /api/jobs` — 提交一批 `{jobs:[{type, prompt, provider?, input_image?, params?, client_ref?}]}` → `{batch_id, jobs:[{job_id, client_ref, status:"queued"}]}`
- `GET /api/jobs/{job_id}` — `{job_id, client_ref, type, provider, status, progress, artifacts:[{kind, path, url, meta}], error, created_at, updated_at}`
- `GET /api/jobs?status=&batch_id=` — 列表过滤
- `GET /api/jobs/batches/{batch_id}` — 批次汇总
- `POST /api/jobs/{job_id}/cancel`

**job.type**: `text_to_image | image_to_image | text_to_video | image_to_video`
**job.provider**: `modelscope | jimeng | volcengine | openai | gemini | runninghub | comfyui`
**status**: `queued → running → succeeded | failed | canceled`

## Provider 路由（复用现有端点）

| (type, provider) | 提交端点 | 轮询 | 取产物 |
|---|---|---|---|
| image / modelscope·jimeng·volcengine·openai·gemini | `POST /api/canvas-image-tasks` | `GET /api/canvas-image-tasks/{id}`（jimeng_pending → `POST /api/jimeng/query-media`） | `result.images[]` |
| video / jimeng·volcengine·openai | `POST /api/canvas-video` | 直接返回 videos 或 `POST /api/jimeng/query-media`(submit_id, kind=video) | `videos[]` / `urls[]` |
| any / runninghub | `POST /api/runninghub/workflow-submit`(需 params.workflowId) | `GET /api/runninghub/query?taskId=` | `data.urls[]` |
| any / comfyui | `POST /api/canvas-comfy-tasks`(需 params.workflow_json) | `GET /api/canvas-comfy-tasks/{id}` | `result.images[]` |

默认路由：t2i/i2i→modelscope，t2v/i2v→jimeng。可 per-job 覆盖 + 失败降级链。

## 作业存储 + 执行器

- **SQLite** `data/jobs.db`（重启不丢；启动时把卡在 running 的重新入队）。
- **进程内 asyncio 执行器**，并发 `JOB_CONCURRENCY`（默认 3），失败指数退避重试 `JOB_MAX_RETRIES`（默认 2）。
- 产物：读现有端点返回的 `/assets/output/xxx` URL → 转本地绝对路径回传（同机模式）。

## 安全加固（落进 main.py）

| 项 | 改法 | 位置 |
|---|---|---|
| 监听 | `host=os.getenv("HOST","127.0.0.1")` | uvicorn.run @15010 |
| 鉴权 | 新增中间件：回环放行；远程需 `X-App-Token==APP_TOKEN` 否则 401；未设 token 拒绝远程 | CORS 之前 |
| CORS | env 驱动 `CORS_ORIGINS`（默认仅本机） | @70-75 |
| 吐密钥 | `/api/config/token` 打码返回 | endpoint |
| 自更新 | `ENABLE_SELF_UPDATE=0` 时 403 | @2098 / schedule_self_restart |

## 无头运行

- `serve.py` 无头入口 + macOS launchd plist（开机自启常驻），跟 sign-bot 的 launchd 玩法一致。
- `.env.example` + `requirements.txt`（服务自带依赖，独立 venv）。

## 测试

- 单元：store 状态机流转/崩溃恢复、routing 选择/降级、models 校验（venv pytest，自包含不 import main.py）。
- API：最小 FastAPI app 挂 jobs router + mock client，验证 submit/poll/list/cancel 契约。
- 集成（需凭证，文档化）：submit 一个 t2i 走 ModelScope 免费跑真链路 → 断言产物文件落地。

## 交付物

`infinite-canvas-gt/jobs/`（models/store/routing/client/worker/api/config）、加固后的 `main.py`、`serve.py`、`launchd/*.plist` + 安装脚本、`.env.example`、`requirements.txt`、`tests/`、`docs/JOB-API.md`（loop 对接指南 + python 示例）。
