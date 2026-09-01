from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
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
    ai_model: str = "openai/gpt-oss-20b"
    ai_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("GROQ_API_KEY", "ai_api_key")
    )
    ai_timeout_ms: int = Field(default=5000, gt=0)
    ai_prompt_version: str = "prompt-v1"
    ai_schema_version: str = "recommendation-v1"
    auth_issuer: str = "recoveryos-local"
    auth_audience: str = "recoveryos-api"
    auth_mode: str = "local"
    auth_jwks_url: str | None = None
    auth_hmac_secret: str | None = None
    rate_limit_max_requests: int = Field(default=120, gt=0)
    rate_limit_window_seconds: int = Field(default=60, gt=0)
    job_lease_seconds: int = Field(default=60, gt=0)
    job_backoff_base_seconds: int = Field(default=30, gt=0)
    job_backoff_max_seconds: int = Field(default=900, gt=0)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        if self.auth_mode not in {"local", "jwks"}:
            raise ValueError("auth_mode must be either local or jwks")
        if self.app_env.lower() == "production":
            if self.auth_mode != "jwks" or not self.auth_jwks_url:
                raise ValueError("production requires auth_mode=jwks and auth_jwks_url")
            if not self.webhook_secret:
                raise ValueError("production requires webhook_secret")
        if self.auth_mode == "jwks" and not self.auth_jwks_url:
            raise ValueError("jwks authentication requires auth_jwks_url")
        if self.ai_provider.strip().lower() == "groq" and not self.ai_api_key:
            raise ValueError("groq AI provider requires GROQ_API_KEY")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
