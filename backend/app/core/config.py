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
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_flash_model: str = "deepseek-v4-flash"
    deepseek_pro_model: str = "deepseek-v4-pro"
    deepseek_timeout_seconds: int = 60
    agent_enabled: bool = False
    cost_approval_threshold: float = 100000.0
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3001"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
