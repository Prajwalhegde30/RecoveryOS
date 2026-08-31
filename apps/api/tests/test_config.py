import pytest
from pydantic import ValidationError

from app.config import Settings


def test_development_configuration_can_use_local_auth() -> None:
    settings = Settings(app_env="development", auth_mode="local")
    assert settings.auth_mode == "local"


def test_jwks_mode_requires_a_discovery_url() -> None:
    with pytest.raises(ValidationError, match="auth_jwks_url"):
        Settings(auth_mode="jwks")


def test_production_requires_jwks_and_webhook_secret() -> None:
    with pytest.raises(ValidationError, match="production requires"):
        Settings(app_env="production", auth_mode="local", webhook_secret=None)


def test_production_accepts_explicit_security_configuration() -> None:
    settings = Settings(
        app_env="production",
        auth_mode="jwks",
        auth_jwks_url="https://identity.example/.well-known/jwks.json",
        webhook_secret="configured-secret",
    )
    assert settings.auth_mode == "jwks"
