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
    video_provider: str = "fake"                      # fake | seedance | aitoearn | faceless
    seedance_model: str = "seedance2.0fast"
    dreamina_bin: str = "dreamina"
    video_output_dir: str = "./data/videos"
    public_base_url: str = "http://127.0.0.1:8010"
    aitoearn_ai_base_url: str | None = None       # AiToEarn AI service base, e.g. http://127.0.0.1:8080/api/ai
    aitoearn_video_model: str = "seedance-1-pro"  # model routed by AiToEarn (Volcengine/Seedance/Sora/...)

    # --- faceless 口播 video (TTS voiceover + inner clip b-roll + burned captions) ---
    tts_provider: str = "auto"            # auto | say | openai | fake
    tts_model: str = ""                   # e.g. "tts-1"; empty disables the openai TTS path
    tts_voice: str = "alloy"
    tts_base_url: str | None = None       # if None, the TTS factory falls back to anthropic_base_url
    tts_api_key: str | None = None        # if None, the TTS factory falls back to anthropic_api_key
    faceless_visual: str = "fake"         # aitoearn | seedance | fake — inner clip provider for b-roll


settings = Settings()
