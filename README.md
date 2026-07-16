# MatrixLoop 矩阵账号自我修正指挥台

自主运行的**多账号内容生产 Loop + Dashboard**。为一组 Web3 出海品牌频道(Airdrop Edge / Clear Charts / Quiet Yield / Aurea)自动完成 **选题 → 脚本 → 生图 → 生视频 → 装配 → 发布**,并用真实流量/粉丝数据回灌形成自我修正闭环,为产品 NINA / Xaue 导流。

> 单机部署、人审为闸(脚本需人工采纳才能生成视频)、按天配额熔断。

---

## 架构

```
frontend/  React + Vite + TS 大屏(选题池 / 制作流水线 / 视频工作台 / 账号流量)
backend/   FastAPI + SQLAlchemy + SQLite,APScheduler 定时 Loop
remotion/  Remotion 品牌模板装配层(ffmpeg 之外的可选出片方案)
scripts/   Palmier 精修计划任务(launchd)
docs/      交付说明 / 演示 / Palmier 精修流程
```

### 视频生产链路

默认 `video_provider=waoowaoo_narrated`:

1. **配音** edge-tts 口播,得到真实旁白时长 `target_duration`。
2. **视觉** WaoowaooBrollProvider 驱动 waoowaoo 的 剧本→分镜→分镜图→i2v 片 流水线。
   - 文本模型:newapi `gemini-2.5-pro`
   - 生图:SiliconFlow `Qwen/Qwen-Image`(带 `negative_prompt` 压制画面幻觉文字)
   - 生视频 i2v:SiliconFlow `Wan-AI/Wan2.2-I2V-A14B`(适配器直调,图片走 base64、内置重试)
3. **拼接** 每个分镜按 `旁白时长 ÷ 分镜数` 分到等长时间片,`setpts` 拉伸填满 —— **画面铺满全片、随脚本推进,与字幕同步,不再循环**。
4. **装配** ffmpeg 烧录 CJK 感知字幕(按标点/词边界断行);或切换 Remotion 品牌模板。
5. **精修(可选,Loop 外)** 送 Palmier Pro(MCP)做 hero 片人工精修出口。

### 治理

- **人审闸**:脚本 `review_status=adopted` 才可生成视频。
- **配额**:每日 全局 / 单账号 / 单频道(vertical)三级上限,环境变量可配。
- **去重**:`sha256(account, script, provider)` 复用已成片;跨账号近似脚本拒绝。
- **真实进度**:provider 回调 `on_progress(stage, pct)` 落库,前端轮询真实进度而非假计时。

---

## 快速开始

### 后端(:8000)

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # 填入 newapi / SiliconFlow / 平台 key(见下)
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

> 无 `--reload`:改 `.env` 后必须重启后端才生效。

### 前端(:5173)

```bash
cd frontend
npm install
npm run dev   # 用 http://localhost:5173 打开(勿用 127.0.0.1)
```

### 测试

```bash
cd backend  && .venv/bin/python -m pytest -q
cd frontend && npm test
```

---

## 配置(`backend/.env`,已 gitignore)

以 `MATRIXLOOP_` 为前缀,详见 `backend/app/config.py`。关键项:

| 变量 | 说明 |
|---|---|
| `MATRIXLOOP_VIDEO_PROVIDER` | `waoowaoo_narrated`(默认链路) |
| `MATRIXLOOP_ANTHROPIC_BASE_URL` / `_API_KEY` | newapi 网关(文本模型) |
| `MATRIXLOOP_WAOOWAOO_SF_API_KEY` | SiliconFlow key(生图 + i2v) |
| `MATRIXLOOP_WAOOWAOO_PANELS` | 每条视频分镜数(控成本/时长) |
| `MATRIXLOOP_VIDEO_MAX_PER_DAY` / `_PER_ACCOUNT_PER_DAY` / `_PER_CHANNEL_PER_DAY` | 每日配额 |
| `MATRIXLOOP_FACELESS_COMPOSITOR` | `ffmpeg`(默认)或 `remotion` |
| `X_BEARER_TOKEN` / `YOUTUBE_API_KEY` / `INSTAGRAM_TOKEN` / `SCRAPECREATORS_API_KEY` | 平台流量数据(可留空) |

**密钥永不入库**:`.env`、`.env.bak*` 均已忽略。

---

## 依赖

- 后端:FastAPI、SQLAlchemy、Pydantic、httpx、Pillow、APScheduler、anthropic
- 外部:**ffmpeg**(装配)、waoowaoo Docker(:13000)、SiliconFlow、newapi
- 可选:Node/Remotion(装配层)、Palmier Pro app(:19789 MCP,精修)

## 数据

SQLite `backend/data/matrixloop.db`(无迁移框架,列变更手动 `ALTER TABLE`)。成片存 `backend/data/videos/`,经 `/media/*` 提供。
