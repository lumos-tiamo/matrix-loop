# MatrixLoop 飞轮 · 演示方案 (Runbook)

一份可照着走的演示脚本。分三层:**A 现在就能演**(无需外部凭证:真 LLM + 真趋势 + 治理化流水线 + 飞轮 UI + autopilot/kill-switch + 闭环)、**B UI 动线**、**C 完整版**(接上 Seedance 真视频 + AiToEarn 真发布 + 无人值守)。建议时长 **12–15 分钟**。

---

## 0 · 演示前准备(约 3 分钟,提前跑好)

```bash
# 1) 后端(从 backend/ 启动才加载 .env 里的真 LLM key),端口 8010
cd ~/matrix-loop/backend
rm -f data/matrixloop.db && ./.venv/bin/python seed_demo.py          # 干净 demo 数据
MATRIXLOOP_DATABASE_URL="sqlite:////Users/aa00102/matrix-loop/backend/data/matrixloop.db" \
  ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 &

# 2) 前端,端口 5173 → 指向 8010
cd ~/matrix-loop/frontend
VITE_API_BASE="http://127.0.0.1:8010" npx vite --host 127.0.0.1 --port 5173 &

# 3) 灌入趋势(演示①要有数据)。两种方式二选一:
#    (a) 稳定可复现:用仓库自带的一批(下面这条)
curl -s -X POST http://127.0.0.1:8010/trends/ingest -H "Content-Type: application/json" -d @docs/demo-trends.json
#    (b) 现场"真爬"炫技:让我(agent)跑 agent-reach 抓当下 crypto 爆款 → POST /trends/ingest
```

体检:`curl -s http://127.0.0.1:8010/health` 有 `{"status":"ok"}`;浏览器开 `http://127.0.0.1:5173/` 能看到飞轮首页。

> 端口坑:`:8000` 被 sign-bot 生产占用,所以后端固定 **:8010**、前端 `VITE_API_BASE` 指 8010。

---

## A · 一键叙事化演示(主线,约 5 分钟)

```bash
cd ~/matrix-loop && bash scripts/demo_flywheel.sh
```

这条脚本会**从头到尾走一遍一条内容**,终端打印每步结果(真实可见):

| 步 | 演示看到什么 | 话术(这步证明了什么) |
|---|---|---|
| ① 爬爆款 | 飞轮 crawl 节点=8,列出真实爆款(CASHCAT/Ansem 空投/Grass…) | "系统抓到当下 crypto 真实爆款,按子垂类喂给选题" |
| ② 定调 | 保存 brief:web3 + 加密交易者/空投/DeFi/Meme + 人设 Nina | "你只设一次定调,后面全自动跟着它走" |
| ③ 脚本 | **真 LLM 脚本**打印出来(吃定调+趋势+历史表现) | "这是真 Claude 现写的、契合定调和当下热点的脚本" |
| ④ 视频 | 成片对象(provider/status/cost/media_url) | "用量治理:预算/配额/去重全在;绝不把 fake 当真发" |
| ⑤ 发布 | 人工审核通过 → 发布返回 **422 未配 AiToEarn** | "人在环;配好 AiToEarn + 开 autopilot 后这步自动真发" |
| ⑥⑦⑧⑨ | 复合分 + 建议(含 `content_performance` 真实表现纠偏) | "真实表现回流→评估→改进建议→喂下一轮,闭环自我修正" |

现场话术收尾:"整条链每一步都是真跑的;只有'真视频画面'和'真发布'两处等外部账号接上。"

---

## B · UI 动线演示(可视化,约 4 分钟)

浏览器 `http://127.0.0.1:5173/`:

1. **飞轮首页(核心)** —— 指着中间的环:"9 步飞轮在转(能量扫掠 + 流向),每个节点是真实计数;`爬爆款`=8 是刚抓的真趋势。核心大数=今日交付。"
2. **顶部 KPI**:今日交付 / 自动驾驶账号 N/M / 待审 / 状态。
3. **右侧「自动驾驶账号」**:点某个号的开关 → 变绿。话术:"打开=这个号下班后全自动跑到发布;不打开=停在审核队列等人。"(切一个开、留一个关做对比)
4. **kill-switch**:点右上 **⏸ 暂停飞轮** → 顶部/核心变"已暂停"、环停 → 再点 **▶ 恢复**。话术:"随时一键刹车,存数据库、重启也记得。"
5. **飞轮流水**:指右下事件流(跑过 A 脚本后会有 script/evaluate 事件)。
6. 顺带切 nav:**视频**(工作台:定调编辑 + 选题→脚本→视频→审核队列)、**导流**(桑基)、**总览**(旧 BI 大屏,已挪 /overview)。话术:"飞轮是指挥台,其它是下钻。"

---

## C · 无人值守演示(约 2 分钟)

不想等定时(默认 180min),现场手动跑一圈 autopilot,让它自动推进 + 流水刷出来:

```bash
# 先在 UI 或 API 把某个号设为 autopilot
curl -s -X POST http://127.0.0.1:8010/accounts/4/autopilot -H "Content-Type: application/json" -d '{"enabled":true}'

# 手动触发一圈编排(等价于调度器到点会做的事;用同一个库)
cd ~/matrix-loop/backend
MATRIXLOOP_DATABASE_URL="sqlite:////Users/aa00102/matrix-loop/backend/data/matrixloop.db" ./.venv/bin/python -c "
from app.db import SessionLocal
from app.orchestrator.engine import run_autopilot_cycle
from app.analysis.factory import resolve_llm_client
from app.video.factory import resolve_video_provider
s=SessionLocal()
rep=run_autopilot_cycle(s, llm=resolve_llm_client(), video=resolve_video_provider(), aitoearn=None, sync=False)
print('processed:', rep['processed'], '| paused:', rep['paused'])
for r in rep['results']:
    print(' ', r['account_id'], '→ reached', r['reached_step'], '|', ' '.join(r['actions']))
"
```

看到 autopilot 号自动走 采纳选题→脚本→视频→审核→(发布因未配 AiToEarn 停在 blocked),每步落审计 `FlywheelEvent`。刷新飞轮首页 → **飞轮流水**多了这些事件。

真无人值守(让调度器自己定时转):

```bash
curl -s -X POST http://127.0.0.1:8010/flywheel/scheduler/start     # 启动定时器
curl -s http://127.0.0.1:8010/flywheel/status                      # {"paused":false,"scheduler_running":true}
curl -s -X POST http://127.0.0.1:8010/flywheel/scheduler/stop      # 演示完停掉
```

话术:"生产上把 `MATRIXLOOP_SCHEDULER_AUTOSTART=true`,进程一起就自动转;autopilot 号无人值守跑完整飞轮,你只看异常和审计。"

---

## D · 完整版演示(接上外部件后,可选/进阶)

三个外部件接上后,同样的动线会从"占位/门控"变成"真画面/真发布":

1. **真视频画面(Seedance/即梦)** —— 换一个**高级会员**即梦号 `dreamina login` → `.env` 设 `MATRIXLOOP_VIDEO_PROVIDER=seedance` → 重启后端。再跑 A 的④,`provider` 变 `seedance`、`media_url` 是 `/media/xxx.mp4` 真文件 → 浏览器点"看成片"直接播。
2. **真发布 + CN 数据(AiToEarn)** —— `docker compose up` 起 AiToEarn、账号在其内扫码连接、`POST /accounts/link-aitoearn`(或手动 external_ref)、`.env` 设 `MATRIXLOOP_AITOEARN_BASE_URL/API_KEY` → A 的⑤从 422 变成真排期/发布,返回 `flowId`;隔段时间 `POST /publish/refresh-analytics` 把真实播放/互动回填 → ⑥⑦⑧⑨ 用真数字自我修正。
3. **真无人值守** —— C 里的 `scheduler_autostart`。

---

## E · 卖点一句话清单(讲给非技术观众)

- **人下班,飞轮不下班**:定调设一次,autopilot 号自动 选题→脚本→视频→发布→复盘→改进,循环。
- **真 AI 不是壳**:脚本是真 Claude 现写、吃当下爆款和历史表现。
- **敢放手是因为有护栏**:绝不发 fake、发布三重门、预算/配额/熔断、矩阵反作弊、一键刹车、全程审计。
- **越跑越准**:真实播放回流→归因到具体选题/脚本→下一轮偏向赢家(闭环)。
- **看得见**:一个会转的飞轮,每步实时数字,谁在跑到第几步一目了然。

---

## F · 故障处理

| 现象 | 处理 |
|---|---|
| 前端打不开 / 数据不对 | 确认后端 :8010 在跑、前端 `VITE_API_BASE=http://127.0.0.1:8010` |
| 改了模型/表后报错 | 重建 DB:`rm -f backend/data/matrixloop.db && cd backend && ./.venv/bin/python seed_demo.py`,重启后端 |
| ③脚本没出来 | LLM 未配:确认从 `backend/` 启动(加载 .env)、`.env` 有 `MATRIXLOOP_ANTHROPIC_API_KEY` |
| ⑤发布 422 | 正常(未配 AiToEarn)——这是诚实门控,不是 bug |
| ④视频是 fake | 正常(未配 Seedance)——接高级即梦号后变真 |
| 端口被占 | `lsof -ti:8010`/`:5173` 找 PID;**勿动 :8000 的 sign-bot 生产进程** |
| 测试自检 | `cd backend && ./.venv/bin/python -m pytest -q`(262 绿) · `cd frontend && npx vitest run`(41 绿) |
