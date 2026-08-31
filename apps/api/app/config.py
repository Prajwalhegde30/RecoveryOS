from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    web_origin: str = "http://localhost:3000"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://recoveryos:recoveryos@localhost:5432/recoveryos"
    webhook_secret: str | None = None
    max_recovery_attempts: int = Field(default=3, gt=0)
    scoring_base_probability_percent: int = Field(default=50, ge=0, le=100)
    scoring_timeout_adjustment_percent: int = Field(default=10, ge=-100, le=100)
    scoring_incident_penalty_percent: int = Field(default=20, ge=-100, le=100)
    scoring_confidence_weight_percent: int = Field(default=50, ge=0, le=100)
    scoring_version: str = "scoring-v1"
    ai_provider: str = "deterministic"
    ai_model: str = ""
    ai_timeout_ms: int | None = Field(default=None, gt=0)
    ai_prompt_version: str = "prompt-v1"
    ai_schema_version: str = "recommendation-v1"
    auth_issuer: str = "recoveryos-local"
    auth_audience: str = "recoveryos-api"
    auth_hmac_secret: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
