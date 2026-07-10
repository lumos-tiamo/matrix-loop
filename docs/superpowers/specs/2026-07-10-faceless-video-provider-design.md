# FacelessVideoProvider 设计文档

**日期:** 2026-07-10 · **状态:** 已定稿,待实现 · **形态:** faceless 口播(AI clip 做画面 + TTS 旁白 + 烧录字幕)

## 目标

给 matrix-loop 增加一条 **faceless 口播** 视频形态:把已生成的脚本合成为一条竖版短视频——
用模型直出的 clip(AiToEarn/Seedance)当背景画面,叠加 TTS 旁白 + 动态字幕,ffmpeg 合成成片。
必须遵循现有「可插拔接缝 + fake 回退」模式(照 `LLMClient`/`VideoProvider`),做到**无外部 key 也能真出片、可测、可交付**。

## 背景与约束(已核实)

- 本机 **ffmpeg 8.1.1 + ffprobe** 可用 → 合成/烧字幕本地可跑。
- 本机 **macOS `say`** 可用 → 零 key 也能出**真英文旁白**(机器音但真实),作为运行时默认。
- newapi 中转当前 **103 个模型但无任何 TTS/audio 模型**(`tts-1`/`gpt-4o-mini-tts` 均 `model_not_found`)。
  中转归用户所有,后续在其上加一个 TTS 通道即可让「复用中转」路径生效。
- 用户已定:真人声主力走 **OpenAI 兼容 `/v1/audio/speech`(复用现有中转 key/base)**;运行时默认回退 `say`。

## 架构:两个新接缝 + 一个新 provider

### 接缝 ①:`TTSProvider`(新目录 `backend/app/video/tts/`)

**协议**(`tts/base.py`):
```python
@dataclass
class TTSResult:
    audio_path: str          # 本地文件路径(wav 或 mp3)
    duration_seconds: float  # 由 ffprobe 实测
    fmt: str                 # "wav" | "mp3"

class TTSProvider(Protocol):
    name: str
    def synthesize(self, *, text: str, voice: str | None = None) -> TTSResult: ...
```

**实现**:
- `FakeTTSProvider`(`tts/fake.py`)——不调外部:用 ffmpeg lavfi 生成一段**静音 wav**,时长 = `max(1.0, round(词数 / 2.7, 2))`。确定性、离线,给测试用。
- `SayTTSProvider`(`tts/say.py`)——把旁白文本**写到临时文件**,`say -f text.txt -o out.aiff`(用 `-f` 读文件,避免长文本的 CLI 转义/长度坑),再 ffmpeg 转 wav;ffprobe 实测时长。零 key,运行时默认。可注入 `run`(命令执行器)以便测试。
- `OpenAITTSProvider`(`tts/openai.py`)——`POST {base}/v1/audio/speech`,body `{model, voice, input, response_format:"mp3"}`,`Authorization: Bearer {key}`;写 mp3,ffprobe 实测时长。可注入 `http_post`。用户选的主力路径;中转配好 TTS 模型即生效。
- `resolve_tts_provider(settings, *, run=None, http_post=None) -> TTSProvider`(`tts/factory.py`)——
  选择序:`tts_provider` 显式指定则用之;否则 `auto`:若 `tts_model` 非空且有 key → openai;否则若本机有 `say` → say;否则 fake。**绝不抛异常**(任一构造失败降级到下一档,最后 fake)。

### 接缝 ②:字幕(`backend/app/video/captions.py`)

- `chunk_caption(text: str, *, max_words: int = 6) -> list[str]`——按句子/短语切成 ≤max_words 词的短块(先按标点断句,长句再按词数切)。
- `build_ass(chunks: list[str], total_seconds: float, *, resolution=(1080,1920)) -> str`——
  按各块**字符长度占比**把 `total_seconds` 分配到每块,生成带样式(底部居中、粗体、描边)的 ASS 字幕文本。空输入返回最小合法 ASS 头(无事件)。

### 新 provider:`FacelessVideoProvider`(`backend/app/video/faceless.py`)

实现现有 `VideoProvider` 协议(`generate(*, script, brief, params) -> VideoResult`),因此治理/护栏/工厂全部原样复用。

**构造**:`FacelessVideoProvider(*, tts, visual, output_dir, public_base_url, run=<ffmpeg 执行器>, resolution=(1080,1920))`
- `tts`:一个 `TTSProvider`。
- `visual`:一个内层 `VideoProvider`(clip 型:aitoearn/seedance/fake),**绝不是另一个 faceless**(防递归)。
- `run`:可注入的命令执行器(默认 `subprocess.run`),便于测试。

**`generate` 流程**:
1. `narration = script`(脚本本身即口播文本;去掉可能的行首标记/标题行)。
2. `tts_result = tts.synthesize(text=narration, voice=params.get("voice"))` → 音频 + 时长 `D`。
3. 取背景画面:
   - `clip = visual.generate(script=script, brief=brief, params=params)`。
   - 若 `clip.media_url` 是 http(aitoearn)→ 下载到临时文件;若是 `/media` 本地 → 直接用;
   - 若 visual 是 fake(无真实画面)→ 用 ffmpeg `lavfi` 生成品牌渐变背景 clip(时长 `D`)。
   - 统一 scale/crop 到 `resolution`,按 `D` 截取或循环。
4. 字幕:`build_ass(chunk_caption(narration), D, resolution=resolution)` → 写临时 `.ass`。
5. ffmpeg 合成:`背景视频 + 音轨(tts_result.audio_path) + -vf ass=<file>` → 输出 mp4 到 `output_dir`,文件名 `faceless_<dedup_key>.mp4`。
6. 返回 `VideoResult(media_url=f"{public_base_url}/media/{fname}", duration=D, cost=clip.cost, provider="faceless", dedup_key=sha1(narration)[:16], metadata={tts_provider, visual_provider, caption_chunks})`(字段严格对齐现有 `VideoResult`:`media_url/duration/cost/provider/dedup_key/metadata`,无 `status`)。

**错误处理**:每个外部步骤(say/openai/下载/ffmpeg)失败即抛带上下文的异常 → 由上游 `generate_video` 治理记为失败,**绝不产出损坏成片**。fake 路径完全离线确定性。

### 配置(`backend/app/config.py` 新增)

- `tts_provider: str = "auto"`(auto|say|openai|fake)
- `tts_model: str = ""`(空 = 不走 openai;例:`tts-1`)
- `tts_voice: str = "alloy"`
- `tts_base_url: str = ""`(空则回退 `anthropic_base_url`)
- `tts_api_key: str = ""`(空则回退 `anthropic_api_key`)
- `faceless_visual: str = "fake"`(aitoearn|seedance|fake —— 内层画面 provider)
- `video_provider` 增加 `"faceless"` 取值。

### 工厂接线(`backend/app/video/factory.py`)

`resolve_video_provider()` 增加分支:`video_provider == "faceless"` → 构造 `resolve_tts_provider(...)` 作为 tts、按 `faceless_visual` 递归解析内层 clip provider(注意:内层解析时把 provider 视作 aitoearn/seedance/fake,绝不再选 faceless),组装 `FacelessVideoProvider`。任一步失败降级到 fake,不抛异常。

## 数据流

```
脚本(已由 LLM 生成)
  → FacelessVideoProvider.generate
      → TTSProvider.synthesize → 音频 + 时长 D
      → 内层 VideoProvider.generate → 背景 clip(下载/生成)
      → captions: chunk + build_ass → .ass
      → ffmpeg 合成(bg + audio + 烧字幕)→ /media/faceless_xxx.mp4
  → VideoResult(provider="faceless")
  → (上游)generate_video 治理:人审门/去重/配额/计量 → VideoAsset
```

## 复用点

- 走现有 `generate_video` 治理(人审门/预算熔断/日配额/去重/限速/计量)**完全不动**——faceless 只是又一个 `VideoProvider`。
- `guardrails.assign_voice` 给每号分配不同 TTS 音色 → 传入 `params["voice"]` 做矩阵反重。
- 内层画面直接复用已有的 `AiToEarnVideoProvider`/`SeedanceVideoProvider`/`FakeVideoProvider`。

## 测试策略

- **头号端到端**(零外部 key):`FakeTTSProvider` + `FakeVideoProvider` 画面 + **真 ffmpeg** → 断言输出 mp4 存在、ffprobe 显示**音轨+视频轨都在**、时长 ≈ D(±容差)。证明整条合成链真能出可播成片。
- `chunk_caption` 单测:标点断句、长句切词、空串。
- `build_ass` 单测:时长分配占比正确、块数、空输入返回合法头。
- `resolve_tts_provider` 工厂选择:显式/auto/降级各路径(用假 settings + 假探测)。
- `SayTTSProvider`/`OpenAITTSProvider`:注入 fake `run`/`http_post`,断言命令行/HTTP body 构造正确(不真调 say/网络)。
- `resolve_video_provider` faceless 分支 + 防递归。

## 文件清单

- 新增:`backend/app/video/tts/__init__.py`、`base.py`、`fake.py`、`say.py`、`openai.py`、`factory.py`
- 新增:`backend/app/video/captions.py`、`backend/app/video/faceless.py`
- 修改:`backend/app/config.py`(新增配置)、`backend/app/video/factory.py`(faceless 分支)
- 新增测试:`backend/tests/test_tts.py`、`test_captions.py`、`test_faceless_video.py`、`test_video_factory.py`(扩展)

## 非目标(YAGNI)

- 不做逐词高亮/卡拉OK级字幕(块级计时足够;有真 word-timestamp 的 TTS 后续可增强)。
- 不做异步 job 模型(沿用现有同步 + 治理;高并发是后续 follow-up)。
- 不做数字人/虚拟主持(那是另一条形态,本 spec 只做 faceless)。
