# Palmier 精修链路（matrix-loop ↔ Palmier Pro）

matrix-loop 是**无人值守的自动 loop**(选题→脚本→视频→审核→发布);Palmier Pro 是**桌面 AI 剪辑器**,通过 MCP 由 Claude(agent)驱动。二者的整合定位:

> **Palmier = 人工/agent 精修出口**(loop 外),给重点成片加品牌、字幕微调、特效、裁剪。**不是** loop 引擎(它是 GUI、一次一个工程)。日常自动批量装配仍走 Remotion / ffmpeg(loop 内)。

## 前置
- Palmier Pro 开着(自动暴露 MCP `http://127.0.0.1:19789/mcp`)。
- Claude Code 已注册:`claude mcp add -s user --transport http palmier-pro http://127.0.0.1:19789/mcp`,重启会话后 `mcp__palmier-pro__*` 工具可用。

## 桥(matrix-loop 后端已实现)
- `GET /video-assets/{id}/palmier-brief` → `{local_path, script, brand{name,color,accent,handle}, account, resolution}`——驱动 Palmier 所需的一切。
- `POST /video-assets/{id}/finish` `{file_path}` → 把 Palmier 导出的成片登记为该 asset 的最终 media(repoint media_url,provider 追加 `+palmier`;文件不在 video_output_dir 会自动拷入)。

## 精修流程(agent 用 Palmier MCP 执行)
1. 选片:`GET /video-assets?account_id=X&review_status=pending`(或 approved)。
2. 取 brief:`GET /video-assets/{id}/palmier-brief` → 拿 `local_path` / `script` / `brand`。
3. Palmier MCP:
   - `manage_project` create/open(aspectRatio `9:16`,quality `1080p`,fps 30)
   - `import_media` `{source:{path: local_path}}` → 轮询 `get_media` 直到 generationStatus 清空
   - `get_timeline` → `add_clips` `[{mediaRef, startFrame:0}]`(视频+联动音轨自动建)
   - `add_texts` 品牌下三分之一(用 brief.brand:name/handle + accent 色;centerY≈0.92)+ 可选钩子标题(取 script 首句,首 3s)
   - `export_project` `{mode:video, codec:H.264, outputPath: <matrix-loop>/backend/data/videos/palmier_{id}.mp4}` → 轮询 `manage_exports` 到 status=complete
4. 回写:`POST /video-assets/{id}/finish {file_path:"palmier_{id}.mp4"}`。
5. 结果:asset.media_url 指向精修片,provider=`...+palmier`;审核/发布流程不变。

## 实测(2026-07-15)
asset 8(Aurea/askaurea)跑通全链:brief→Palmier(建9:16工程+导入matrix-loop成片+加绿色 `Aurea @askaurea` 下三分之一)→导出 palmier_8.mp4(61.5MB)→finish 回写→`:8000/media/palmier_8.mp4` 200 可播。

## 备注
- Palmier `canGenerate:true`(账号已登录订阅)→ 也能在时间线内用 Kling/Seedance/Veo 生成补拍素材(`list_models` 先看)。
- 想批量:Palmier 一次一工程,适合逐条精修;要自动化可由「计划任务里的 Claude Code(带 palmier MCP)」逐个 asset 跑本流程。
