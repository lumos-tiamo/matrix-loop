from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MATRIXLOOP_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/matrixloop.db"
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    llm_model: str = "claude-sonnet-4-6"
    x_bearer_token: str | None = None
    scrapecreators_api_key: str | None = None
    aitoearn_base_url: str | None = None
    aitoearn_api_key: str | None = None
    youtube_api_key: str | None = None
    instagram_token: str | None = None
    instagram_business_id: str | None = None
    schedule_interval_minutes: int = 360
    schedule_max_accounts: int | None = None

    orchestrator_interval_minutes: int = 180
    orchestrator_allow_fake_publish: bool = False

    scheduler_autostart: bool = False

    # Video generation
    video_provider: str = "fake"                      # fake | seedance | aitoearn | faceless | runninghub | avatar | waoowaoo_narrated
    seedance_model: str = "seedance2.0fast"
    dreamina_bin: str = "dreamina"
    video_output_dir: str = "./data/videos"
    public_base_url: str = "http://127.0.0.1:8010"
    aitoearn_ai_base_url: str | None = None       # AiToEarn AI service base, e.g. http://127.0.0.1:8080/api/ai
    aitoearn_video_model: str = "seedance-1-pro"  # model routed by AiToEarn (Volcengine/Seedance/Sora/...)

    # Per-account override: these handles use the Aurea digital-host (avatar) provider,
    # regardless of the global video_provider. Comma-separated handles (e.g. "askaurea").
    # Everything else uses video_provider. Lets one loop drive Aurea(avatar) + X/IG(other).
    avatar_handles: str = "askaurea"

    # --- image generation (Aurea 定妆图 / IG carousel) ---
    image_provider: str = "fake"                      # fake | newapi | canvas
    image_model: str = "nano-banana-pro-preview"      # newapi model id (chat-completions image)
    # newapi gateway reused from anthropic_base_url / anthropic_api_key (same relay)

    # canvas = Infinite-Canvas-GT headless aggregator (modelscope/jimeng/volc/gemini)
    # over loopback HTTP. Parallel to newapi — pick via image_provider=canvas.
    canvas_base_url: str = "http://127.0.0.1:3000"
    canvas_app_token: str = ""                        # empty on loopback (auth bypassed)
    canvas_image_provider: str = "modelscope"         # provider routed inside canvas for images

    # --- RunningHub (lip-sync digital human / image-to-video) via API — P3 ---
    runninghub_api_key: str | None = None
    runninghub_base_url: str = "https://www.runninghub.cn"   # account balance/coins live on the .cn region
    runninghub_lipsync_workflow_id: str | None = None
    runninghub_i2v_workflow_id: str | None = None

    # --- faceless 口播 video (TTS voiceover + inner clip b-roll + burned captions) ---
    tts_provider: str = "auto"            # auto | say | openai | fake
    tts_model: str = ""                   # e.g. "tts-1"; empty disables the openai TTS path
    tts_voice: str = "alloy"
    tts_base_url: str | None = None       # if None, the TTS factory falls back to anthropic_base_url
    tts_api_key: str | None = None        # if None, the TTS factory falls back to anthropic_api_key
    faceless_visual: str = "fake"         # aitoearn | seedance | fake — inner clip provider for b-roll
    # final-mux layer: ffmpeg (built-in) or remotion (React brand templates, headless render)
    faceless_compositor: str = "ffmpeg"   # ffmpeg | remotion
    remotion_dir: str = "../remotion"     # relative to backend CWD (matrix-loop/remotion)
    remotion_node_bin: str = "node"

    # --- waoowaoo AI-film b-roll (drama clips as faceless background) ---
    # video_provider="waoowaoo_narrated" = faceless(TTS+captions) with a WaoowaooBrollProvider
    # visual: matrix-loop drives waoowaoo's novel->script->storyboard->panel-image->Kling-clip
    # pipeline over its internal HTTP API, ffmpeg-concats the panel clips into one vertical
    # b-roll, then lays the TTS narration + captions on top. AI-model keys live inside
    # waoowaoo (a pre-provisioned service user), never here.
    waoowaoo_base_url: str = "http://127.0.0.1:13000"
    waoowaoo_internal_token: str = ""     # waoowaoo INTERNAL_TASK_TOKEN (x-internal-task-token)
    waoowaoo_user_id: str = ""            # waoowaoo service-account userId (x-internal-user-id)
    waoowaoo_panels: int = 6              # max panels imaged+filmed per video (caps cost/length)
    # video governor daily caps (per UTC-day; count ready+generating)
    video_max_per_day: int = 20           # global across the whole matrix
    video_per_account_per_day: int = 2    # per account
    video_per_channel_per_day: int = 10   # per account.vertical
    waoowaoo_locale: str = "en"           # locale sent to waoowaoo (script/storyboard prompt language)
    # Video i2v runs through SiliconFlow directly (waoowaoo can't drive SF's POST-body status
    # polling). Panel images come from waoowaoo (its image model can be SF via openai-compat).
    waoowaoo_sf_api_key: str = ""
    waoowaoo_sf_base_url: str = "https://api.siliconflow.cn/v1"
    waoowaoo_sf_video_model: str = "Wan-AI/Wan2.2-I2V-A14B"


settings = Settings()
