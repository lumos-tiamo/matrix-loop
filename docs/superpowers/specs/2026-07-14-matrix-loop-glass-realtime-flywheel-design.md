# matrix-loop 前端玻璃化改造 + 实时飞轮

**日期**: 2026-07-14
**位置**: `~/matrix-loop/frontend/`（+ `backend/app/` 少量新端点）
**状态**: 设计已确认（视觉方向 B + 飞轮 v2 样稿用户已通过），进入实现计划

## 背景与动机

用户想让 matrix-loop 前端 UI 对齐 waoowaoo（[[nina-xaue-octok-products]] 出海矩阵的 AI 影视工具）的高级创作工具观感。核心痛点：**飞轮页(Flywheel)又丑、又只是聚合计数的"摆设"，看不到自动驾驶账号的实时数据**。

> 关于把 waoowaoo 引擎整合进 matrix-loop 视频模块的结论：**不整合**。两者是不同产品(长篇剧情短剧 vs 自动矩阵单条短视频)、不同技术栈(Next/TS vs Python FastAPI)、不同颗粒度。可取的是它的 **UI/UX 设计**（本 spec）和（未来）它的 provider 适配层作参考。详见对话分析。

## 关键决策（brainstorm 结论）

| 维度 | 决定 |
|---|---|
| 视觉方向 | **B · 深色玻璃融合**——保留 matrix-loop 深色底，采纳 waoowaoo 玻璃质感 + 蓝色渐变主色 + 圆润柔边；数据可视化色(青/绿/紫/琥珀/荧光绿)保留用于状态与 ECharts |
| 范围 | **完整体**：全站玻璃化 + 飞轮实时化 + 视频工作台对齐 |
| 实时机制 | **轮询**（每 3-5 秒拉增量），非 SSE/WS |
| 飞轮信息 | 逐账号活卡片：8步进度轨、状态、已用时/卡住时长、KPI(粉丝+涨幅/播放/综合分)、**本轮成本**、**发布平台**、**下一轮倒计时**、数据新鲜度 |

飞轮 v2 高保真样稿已通过，存于 `.superpowers/brainstorm/47537-1784011218/content/flywheel-v2.html`（作为实现视觉基准）。

## ① 全局玻璃设计系统（方向 B）

新建 `frontend/src/styles/glass-tokens.css`（CSS 变量），并在 `tailwind.config.ts` 用 `theme.extend` 接入（**不升级 Tailwind v4**，避免动构建）。核心 token（取自已通过样稿）：

```
背景：#070b14 + 三层径向辉光(蓝#2f7bff@.22 左上 / 紫#A78BFA@.16 右上 / 青#4CD4F0@.10 底部)
玻璃面：linear-gradient(160deg, rgba(255,255,255,.075), rgba(255,255,255,.028))
        border 1px rgba(255,255,255,.10)；radius 20px；backdrop-blur(22px) saturate(140%)
        shadow 0 24px 48px -18px rgba(0,0,0,.55) + inset 0 1px 0 rgba(255,255,255,.09)
主色渐变：#2f7bff → #5ca8ff（来自 waoowaoo）
状态色：running=青#4CD4F0 · ok=绿#38E08A · blocked=琥珀#FFB020 · error=红#FF5C7A
数据色：综合分=荧光绿#B6FF3C · 辅助=紫#A78BFA
文本：#EAF0FA / muted #93A0B8 / dim #5C6579
字体：Inter(UI) + JetBrains Mono(数字/时间戳) + Noto Sans SC(中文)
```

共享组件（`frontend/src/components/`）改造为玻璃版，**所有页面通过它们自动继承新外观**：
- `GlassCard`（替代 `ChartCard`，保留 title/pill API 兼容）
- `GlassButton`（primary 渐变 / secondary / ghost / tone-*）
- `StatusPill`、`GlassChip`、`StatTile`（重绘）
- `Layout`/顶栏导航 → 玻璃 pill 风

## ② 实时飞轮（后端 + 前端）

**后端**（`backend/app/api/` + `backend/app/orchestrator/state.py`）——数据都现成，只新增读接口、不重采：

- `GET /flywheel/accounts` → 逐账号当前状态数组，每项：
  `{account_id, platform, handle, autopilot, status(running|blocked|ok|error|idle), current_step, step_index, steps_done, elapsed_sec, blocked_reason, last_event{step,status,detail,ts}, kpis{followers, followers_delta, views_7d, score}, cost_cycle, next_run_eta_sec, synced_at}`
  数据源：`flywheel_events`(取每账号最新 cycle 的步进) + `loop_runs` + `evaluations`(综合分) + `snapshots`(粉丝/播放/新鲜度) + `video_assets.cost`(本轮成本) + scheduler interval(下一轮 ETA)。
- `GET /flywheel/events?since=&account_id=&limit=` → 增量事件（带账号 handle 上下文），供事件流轮询。
- 扩展 `GET /flywheel`：加 `today_cost`、全局计数(在飞/待审/已完成)。

**前端**（`frontend/src/`）：
- `hooks/usePolling.ts`：`usePolling(fn, 4000)`，标签页隐藏时暂停、重新可见即刷。
- 重写 `pages/Flywheel.tsx` 按 v2 样稿：顶栏玻璃 pill(LIVE 脉冲 + 今日成片/成本/自驾数/待审 + 暂停) + 两栏(逐账号活卡片列 + 实时事件流 aside)。
  - 账号卡：展开态(running/blocked)含头像/handle/平台芯片/状态 pill/已用时或卡住时长/8步珠子轨道/指标条(粉丝+涨幅、播放、综合分、本轮成本、下一轮倒计时、同步新鲜度)/阻塞行动条；折叠态(ok)迷你行。
  - `StepTracker` 组件（8 步：sync→evaluate→topic→script→video→approve→publish→track）。
  - 倒计时用本地 tick + 轮询校正。

## ③ 视频工作台对齐

用新玻璃组件重绘 `pages/Video.tsx`（频道定调 / 草稿流 / 成片审核），与飞轮同一设计语言。

## ④ 其余页面

总览/导流/爆文库/对比/下钻：替换为共享玻璃组件 + token 即自动升级；ECharts 套一份深色玻璃主题(`echarts-glass-theme.ts`：透明底、玻璃色系、辉光)。

## 测试

- 后端 pytest：`/flywheel/accounts` 聚合(running/blocked/ok/error 各态归类正确、KPI/成本/下一轮字段)、`/flywheel/events` 增量(since 过滤、account 过滤)。
- 前端 vitest：`usePolling`(定时/可见性暂停)、账号卡三态渲染、`StepTracker` 步进映射。

## 交付物

`frontend/src/styles/glass-tokens.css`、`echarts-glass-theme.ts`、玻璃版共享组件、`hooks/usePolling.ts`、重写的 `Flywheel.tsx` + 玻璃化 `Video.tsx` 与其余页、后端 2 个新端点 + `/flywheel` 扩展、前后端测试。

## 非目标（YAGNI）

- 不整合 waoowaoo 引擎、不引入 SSE/WebSocket、不升级 Tailwind v4、不做 Remotion 时间轴编辑器。
