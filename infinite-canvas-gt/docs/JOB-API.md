# 内容作业 API — matrix-loop 对接指南

把 Infinite-Canvas-GT 当成一个**无头生成引擎**：matrix-loop 提交一批 prompt，轮询到完成，读本地产物路径。各家 provider 的差异全被藏在服务里。

## 一、启动无头服务（同机）

```bash
cd ~/matrix-loop/infinite-canvas-gt
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example API/.env          # 填 MODELSCOPE_API_KEY 等凭证
.venv/bin/python serve.py         # 监听 127.0.0.1:3000（回环免 token）
```

常驻服务（开机自启 + 崩溃重拉）：

```bash
bash launchd/install.sh
```

## 二、契约

| 端点 | 说明 |
|---|---|
| `POST /api/jobs` | 提交一批 → `{batch_id, jobs:[{job_id, client_ref, status, provider, type}]}` |
| `GET /api/jobs/{job_id}` | 单作业状态 + `artifacts:[{kind, path, url, meta}]` |
| `GET /api/jobs?status=&batch_id=` | 列表过滤 |
| `GET /api/jobs/batches/{batch_id}` | 批次汇总 `{total, counts, done}` |
| `POST /api/jobs/{job_id}/cancel` | 取消未完成作业 |

**作业规格**（POST body 里 `jobs[]` 的每一项）：

```jsonc
{
  "type": "text_to_image | image_to_image | text_to_video | image_to_video",
  "prompt": "a cyberpunk host in neon city",
  "provider": "modelscope",          // 可省，按 type 默认：图→modelscope，视频→jimeng
  "input_image": "/assets/output/ref.png",  // i2i / i2v 必填
  "params": {                         // 透传给引擎，按 provider 取用
    "model": "Tongyi-MAI/Z-Image-Turbo",
    "size": "1024x1024", "n": 1,
    "duration": 5, "aspect_ratio": "16:9", "resolution": "720p",
    "workflowId": "2058...",          // runninghub 必填
    "workflow_json": "Z-Image.json"   // comfyui 用
  },
  "client_ref": "loop-task-8899"      // 你的关联ID，回填用
}
```

**状态机**：`queued → running → succeeded | failed | canceled`
**产物**：`artifacts[].path` 是本地绝对路径（同机直接读），`artifacts[].url` 是服务内 `/assets/output/...`。

## 三、provider 路由

| type + provider | 底层复用的现有端点 |
|---|---|
| 图片 · modelscope/jimeng/volcengine/openai/gemini | `/api/canvas-image-tasks`（jimeng 云队列自动兜底 `query-media`） |
| 视频 · jimeng/volcengine/openai | `/api/canvas-video`（jimeng 返回 submit_id 再轮询） |
| 任意 · runninghub | `/api/runninghub/workflow-submit` + `query`（需 `params.workflowId`） |
| 任意 · comfyui | `/api/canvas-comfy-tasks`（需 `params.workflow_json`） |

默认路由：t2i/i2i→modelscope，t2v/i2v→jimeng。视频主力失败自动降级到 runninghub。逐作业可用 `provider` 覆盖。

## 四、loop 里怎么用（Python）

`clients/matrix_loop_client.py` 是零依赖客户端，import 即用：

```python
from matrix_loop_client import ContentClient

client = ContentClient()   # 同机回环，免 token

# 单个：出图
arts = client.generate("a serene mountain lake, cinematic", type="text_to_image")
scene_path = arts[0]["path"]          # 本地绝对路径

# 图生视频（虚拟主持人动起来）
clips = client.generate(
    "the host smiles and gestures", type="image_to_video",
    provider="jimeng", input_image=scene_path,
    params={"model": "3.0", "duration": 5, "aspect_ratio": "9:16"},
)

# 批量：一次投 N 个 prompt，并发跑
batch = client.submit([
    {"type": "text_to_image", "prompt": p, "client_ref": f"scene-{i}"}
    for i, p in enumerate(prompts)
])
records = client.wait_batch([j["job_id"] for j in batch["jobs"]])
for r in records:
    if r["status"] == "succeeded":
        use(r["client_ref"], r["artifacts"][0]["path"])
```

## 五、curl 速查

```bash
# 提交
curl -s localhost:3000/api/jobs -H 'content-type: application/json' \
  -d '{"jobs":[{"type":"text_to_image","prompt":"a red panda","client_ref":"t1"}]}'
# 轮询
curl -s localhost:3000/api/jobs/<job_id>
```

局域网/远程调用时：服务端设 `APP_TOKEN=xxx`，请求带 `-H 'X-App-Token: xxx'`。

## 六、安全默认（同机部署）

- 监听 `127.0.0.1`，回环放行、远程需 `X-App-Token`；未设 token 则拒绝一切远程。
- CORS 默认仅本机；`/api/config/token` 仅本机回明文、远程打码。
- 无头服务默认 `ENABLE_SELF_UPDATE=0`（关掉 GitHub 自更新这个 RCE 面）。
