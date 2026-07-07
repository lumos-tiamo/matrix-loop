from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MATRIXLOOP_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/matrixloop.db"
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    llm_model: str = "claude-sonnet-4-6"
    x_bearer_token: str | None = None
    scrapecreators_api_key: str | None = None
    schedule_interval_minutes: int = 360
    schedule_max_accounts: int | None = None


settings = Settings()
