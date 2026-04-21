from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://intern:intern@localhost:5432/internship"
    groq_api_key: str = ""
    env: str = "development"
    max_drafts_per_day: int = 10
    discovery_interval_hours: int = 6
    ranking_interval_hours: int = 1
    log_level: str = "INFO"
    session_secret: str = "changeme"


settings = Settings()
