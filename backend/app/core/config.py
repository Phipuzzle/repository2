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
    query_cache_ttl_seconds: int = 300
    conversation_context_turns: int = 5
    demo_scale: int = 5
    demo_years: int = 5
    sse_poll_interval_seconds: float = 0.5
    sse_heartbeat_seconds: int = 15
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_flash_model: str = "deepseek-flash"
    deepseek_pro_model: str = "deepseek-v4-pro"
    deepseek_timeout_seconds: int = 60
    deepseek_max_tokens: int = 4096
    agent_enabled: bool = False
    agent_demo_anonymous_read: bool = False
    cost_approval_threshold: float = 100000.0
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    oidc_algorithms: list[str] = ["RS256"]
    oidc_jwks_cache_seconds: int = 300
    embedding_provider: str = "hash"
    embedding_model_id: str = "BAAI/bge-small-zh-v1.5"
    embedding_dimension: int = 512
    embedding_model_source: str = "huggingface"
    metadata_retrieval_top_k: int = 8
    slo_lookback_minutes: int = 1440
    slo_agent_p95_seconds: float = 30.0
    slo_agent_error_rate: float = 0.2
    slo_deepseek_p95_seconds: float = 20.0
    slo_deepseek_error_rate: float = 0.2
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3001"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
