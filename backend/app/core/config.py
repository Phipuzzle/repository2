from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Intelligent Data Agent API"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://ida:ida@localhost:5432/intelligent_data_agent"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3002"]
    query_default_limit: int = 100
    query_max_limit: int = 1000
    query_timeout_seconds: int = 15
    sse_poll_interval_seconds: float = 0.5
    sse_heartbeat_seconds: int = 15

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
