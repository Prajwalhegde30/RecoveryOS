from __future__ import annotations

from app.ai.provider import AIProvider, GroqTransport, ProviderAdapter, ProviderTransport
from app.config import Settings


def configured_ai_provider(
    settings: Settings, *, transport: ProviderTransport | None = None
) -> AIProvider | None:
    """Build the configured AI boundary; ``None`` deliberately selects fallback mode."""

    mode = settings.ai_provider.strip().lower()
    if mode == "deterministic":
        return None
    if mode == "groq":
        if not settings.ai_api_key:
            raise ValueError("groq AI provider requires GROQ_API_KEY")
        return ProviderAdapter(
            GroqTransport(
                api_key=settings.ai_api_key,
                model=settings.ai_model,
                timeout_seconds=settings.ai_timeout_ms / 1000,
            ),
            timeout_seconds=settings.ai_timeout_ms / 1000,
            prompt_version=settings.ai_prompt_version,
            model_version=settings.ai_model,
            schema_version=settings.ai_schema_version,
        )
    if mode != "transport":
        raise ValueError("ai_provider must be deterministic, groq, or transport")
    if transport is None:
        raise ValueError("transport AI mode requires an application-provided transport")
    if not settings.ai_model:
        raise ValueError("transport AI mode requires ai_model")
    return ProviderAdapter(
        transport,
        timeout_seconds=settings.ai_timeout_ms / 1000,
        prompt_version=settings.ai_prompt_version,
        model_version=settings.ai_model,
        schema_version=settings.ai_schema_version,
    )
