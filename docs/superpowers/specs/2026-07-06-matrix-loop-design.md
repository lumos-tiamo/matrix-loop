# MatrixLoop 设计文档

- 日期：2026-07-06
- 状态：设计已与用户确认，待用户复核后进入实现计划
- 一句话：一个完整集成的多平台矩阵账号「自我修正 Loop + Dashboard」系统 - 评估单账号价值 → 数据分析 → 自动纠偏账号定位与内容方向并起草下一批内容 → 好看的多账号看板，架构奔着 500 账号无人值守。

## 1. 目标与范围

**要做的（完整体，一个集成系统，不分期交付）：**
- 覆盖平台：小红书、抖音、微信视频号、微信公众号、TikTok、Twitter/X
- 规模：当前约 15 个账号，架构目标 500 个
- 能力链：单账号价值评估 → 数据分析 → 自我修正 Loop（纠偏定位 + 内容方向）→ 生产调度（定时无人值守）
- Loop 每轮产出（用户选定 B 档）：诊断 + 纠偏建议（定位 / 内容方向 / 发布节奏）+ **起草下一批选题与内容脚本**，进入待审核，人审核后自行发布
- Loop 为**多目标**优化：涨粉速度、互动与曝光、商业价值、定位清晰度/垂直度（权重可按账号配置）

**明确不做 / 边界（v1）：**
- Loop **永不自动发布**内容 - 起草产物一律人在环审核（这是设计约束，不是缺陷）
- **不承诺**每个平台第一版都全自动抓数 - 自动抓取稳定性受各平台 API/反爬制约（尤其小红书、抖音、视频号），因此数据接入层做成可插拔连接器 + 手动导入兜底，逐平台从"手动/半自动"升级为"全自动"，系统整体从第一天即完整可用。

## 2. 技术栈

- 后端：Python 3.12 · FastAPI（API）· SQLAlchemy · SQLite（默认）→ Postgres（规模化）· APScheduler（定时）
- LLM：Claude（Anthropic）- 承担评估、分析、起草；输出走结构化 schema 校验
- 前端：Vite · React · TypeScript · Tailwind · ECharts

**仓库结构（`~/matrix-loop/`）：**
```
matrix-loop/
├─ backend/    # FastAPI · connectors · loop engine · evaluation/analysis · llm · scheduler
├─ frontend/   # Vite + React dashboard
├─ data/       # SQLite（gitignored）
└─ docs/       # spec 与说明
```

## 3. 数据模型（系统契约 - 一切挂在它上面）

平台无关的核心字段统一，平台特有字段进 `extra` JSON。

- **Account** — 账号：`id, platform, handle, vertical(垂类), positioning(当前定位描述), objective_weights{涨粉,互动,商业,定位}, acceptance_criteria(验收标准), created_at`
- **Snapshot** — 账号某时刻指标（时间序列，涨粉曲线来源）：`id, account_id, ts, followers, views, engagement_rate, hit_rate(爆文率), conversions/leads, source_tier(api|scrape|manual), extra`
- **ContentItem** — 单条内容表现（爆文与内容方向分析）：`id, account_id, platform_post_id, published_at, type, topic/tags, views, likes, comments, saves, extra`
- **Evaluation** — 单账号价值评估（每轮一版，可对比）：`id, account_id, loop_run_id, composite_score, breakdown{涨粉,互动,商业,定位}, created_at`
- **LoopRun** — 一轮循环记录：`id, account_id, ts, inputs_ref, diagnosis, verify_result{改善?哪些建议见效}, tokens_cost, status(ok|no_progress|error|budget_stop)`
- **Recommendation** — 纠偏建议：`id, loop_run_id, kind(定位|内容方向|节奏), content, status(待执行|已采纳|见效|无效|否决)`
- **Draft** — 起草产物：`id, loop_run_id, kind(选题|脚本), content, review_status(待审|采纳|否决)`

## 4. 自我修正 Loop（心脏）

每个账号每轮 7 步（对应成熟范式：Osmani 五模块+记忆、Claude Code `/goal` 的独立验证、Ralph 的护栏）：

1. **目标** — 读该账号的 `objective_weights` + `acceptance_criteria`。人写验收标准，Loop 负责达成。
2. **采集** — 取最新 Snapshot + 近期 ContentItem（连接器自动 / 上次导入）。
3. **评估** — 计算复合价值分（四目标加权）+ 分项拆解，写入 Evaluation。
4. **分析** — LLM + 指标：识别当前定位、拆解爆文与内容方向、找出与目标的差距。
5. **产出（B）** — 诊断 + Recommendation（定位/内容方向/节奏）+ Draft（下一批选题与脚本）→ 全部置为待审。
6. **验证** — 只取**已采纳并执行**的上一轮建议，比对复合分是否上升；用独立判定（非自评）标每条建议见效/无效。
7. **记忆** — 将"试过什么、结果如何、采纳/否决了什么"持久化到账号记忆，喂回下一轮，避免重复无效建议。

**护栏（防止烧钱死循环）：**
- 每轮最大 turn 上限
- 成本上限：每轮 + 全局 token 预算，超限即停并告警
- 无进展检测：连续 N 轮复合分不涨 → 停止盲目建议，升级策略或标记「需人介入」
- 账号级隔离：单账号/单平台抓数或 LLM 失败不拖垮整批
- 人在环：Draft 必须人审核通过；Loop 永不自动发布

## 5. 数据接入（连接器框架 - 唯一受外部制约层）

- 统一接口 `Connector.fetch(account) -> RawData`；`Normalizer` 归一化成 Snapshot / ContentItem。
- 每平台一个连接器实现，标注「当前档位」（Dashboard 可见、随时升级）：

| 平台 | v1 路线 | 备注 |
|---|---|---|
| Twitter/X | API | 可真自动 |
| TikTok | 抓取（ScrapeCreators 类） | 较可行 |
| 微信公众号 | 官方数据 + 第三方 | 半自动 |
| 小红书 / 抖音 / 视频号 | 半自动 / 手动导入起步 | 反爬严，逐步升级为自动 |

- **手动导入兜底**：CSV / 粘贴 / 截图 OCR，任何平台卡住都能喂数，保证系统完整可用。

## 6. Dashboard

**页面一 · 总览（C 待办队列 + A 全量表格）：**
- 顶部：矩阵健康（按平台/目标达标率）+ 大盘涨粉曲线 + 护栏/成本状态
- 中部「今天需要你处理」队列：待审草稿、无进展告警、待采纳建议（每项带操作按钮）
- 底部：全量账号表，可排序/筛选/虚拟滚动（价值分、粉丝、涨粉%、互动%、爆文、定位、Loop 状态、数据档位），扛 500

**页面二 · 单账号下钻：**
- KPI（粉丝/互动/爆文率/商业）+ 涨粉与互动趋势曲线
- 评估雷达拆解（涨粉·互动·商业·定位）
- Loop 历史时间线（哪轮改了啥、是否见效）
- 本轮待审产出：诊断 + 建议 + 起草选题/脚本，一键采纳/否决

## 7. 错误处理

- 账号级隔离 + 重试/退避；连接器失败仅将该账号标「数据过期」，不炸整批
- LLM 产出走结构化 schema 校验，不合法则重试，杜绝乱输出
- 全量审计日志：每轮 LoopRun 存输入/输出/成本，可追溯
- 护栏触发（超预算/无进展）→ 告警，不静默吞掉

## 8. 测试策略

- 单元：评估算分、分析、验证逻辑，用固定 fixture 快照喂入、结果可断言
- 连接器契约测试：录制样例数据，保证归一化正确
- 护栏测试：构造「无进展/超预算」场景，确认正确刹车
- 端到端：先在现有约 15 个真实账号上跑，人工核对建议质量

## 9. 组件边界（可独立理解与测试）

| 组件 | 职责 | 接口 | 依赖 |
|---|---|---|---|
| Connector（每平台） | 拉原始数据 | `fetch(account)->RawData` | 平台 API/抓取/导入 |
| Normalizer | 原始数据→统一 schema | `normalize(raw)->Snapshot/ContentItem` | schema |
| EvaluationEngine | 复合价值评分 | `evaluate(account,snapshots)->Evaluation` | 数据模型 |
| AnalysisEngine | 定位/内容分析 | `analyze(account,data)->Analysis` | LLM |
| LoopEngine | 编排 7 步 + 护栏 | `run(account)->LoopRun` | 上述 + 记忆 |
| RecommendationStore | 建议/草稿 + 审核状态 | CRUD | DB |
| Scheduler | 定时批量跑 | APScheduler jobs | LoopEngine |
| API | 前端数据/操作 | FastAPI routes | DB |
| Dashboard | 可视化 + 审核操作 | REST | API |

## 10. 建造顺序（完整体内部的 build order，不是砍范围）

schema/数据模型 → 评估 + 分析引擎 → LoopEngine + 护栏 + 记忆 → API → Dashboard（两页）→ 连接器（先手动导入 + Twitter API + TikTok 抓取，其余逐步）→ Scheduler/生产调度。每一步都能在现有约 15 账号上验证。

## 11. 风险与诚实标注

- **抓取稳定性**：小红书/抖音/视频号反爬严，自动抓取不完全由本代码决定 → 连接器 + 手动兜底 + 可升级路径。
- **LLM 成本**：500 账号 × 定时 Loop 的 token 成本需靠护栏（每轮/全局预算）约束；Dashboard 实时展示成本。
- **规模化存储/调度**：SQLite 起步，账号量或并发上来后迁 Postgres；调度需并发与限流。
- **建议质量**：Loop 价值取决于"验证"环真实反馈，v1 需在真实账号上人工校准评估/建议逻辑。
