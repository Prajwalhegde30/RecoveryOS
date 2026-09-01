from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from app.ai.contracts import ActionType, RecommendationEvidence, RecommendationOutput


class AIProviderError(Exception):
    """Base error for failures at the AI provider boundary."""


class AITimeoutError(AIProviderError):
    """The provider did not return within the configured timeout."""


class AIOutputValidationError(AIProviderError):
    """The provider response was not a safe recommendation contract."""


class AITransportError(AIProviderError):
    """The provider transport failed without exposing provider details."""


class AIAuthenticationError(AITransportError):
    """The provider rejected the configured credential."""


class AIRateLimitError(AITransportError):
    """The provider rate limit was reached."""


class AIProviderResponseError(AITransportError):
    """The provider returned an unsuccessful response."""


class AIProvider(Protocol):
    def recommend(self, evidence: RecommendationEvidence) -> RecommendationOutput:
        """Return a validated proposal or raise a typed provider error."""


ProviderTransport = Callable[[dict[str, Any]], object]


GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_SYSTEM_PROMPT = """You are the RecoveryOS advisory recovery-strategy engine.

Analyze only the structured recovery evidence provided by RecoveryOS. Return exactly one
JSON object matching the supplied schema. Recommend only a registered RecoveryOS action.
You are advisory: never execute an action, initiate a payment, send a message, determine
payment truth or recovered revenue, change amounts or recipients, bypass policy or
authorization, or invoke tools. Do not invent facts or include secrets or personal data.
The deterministic RecoveryOS policy engine has final authority over every recommendation.
"""


def groq_recommendation_schema() -> dict[str, Any]:
    """Return the provider-facing schema; versions remain server-controlled."""

    action_values = [action.value for action in ActionType]
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {"type": "string", "enum": action_values},
            "parameters": {"type": "object"},
            "reason_code": {"type": "string"},
            "rationale": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "confidence_percent": {"type": "integer", "minimum": 0, "maximum": 100},
            "fallback_action": {"type": "string", "enum": action_values},
            "prompt_version": {"type": "string"},
            "model_version": {"type": "string"},
            "schema_version": {"type": "string"},
        },
        "required": [
            "action",
            "parameters",
            "reason_code",
            "rationale",
            "evidence",
            "confidence_percent",
            "fallback_action",
            "prompt_version",
            "model_version",
            "schema_version",
        ],
    }


class GroqTransport:
    """Small standard-library Groq client using the official OpenAI-compatible endpoint."""

    def __init__(self, *, api_key: str, model: str, timeout_seconds: float) -> None:
        if not api_key:
            raise ValueError("Groq API key is required")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def __call__(self, evidence: dict[str, Any]) -> object:
        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": GROQ_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(evidence, separators=(",", ":"))},
            ],
            "temperature": 0,
            "stream": False,
            "tool_choice": "none",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "recoveryos_recommendation",
                    "strict": False,
                    "schema": groq_recommendation_schema(),
                },
            },
        }
        request = Request(
            GROQ_CHAT_COMPLETIONS_URL,
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "RecoveryOS/0.1.0",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise AIAuthenticationError("Groq authentication failed") from exc
            if exc.code == 429:
                raise AIRateLimitError("Groq rate limit reached") from exc
            raise AIProviderResponseError("Groq request failed") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise AITransportError("Groq network request failed") from exc
        except json.JSONDecodeError as exc:
            raise AIOutputValidationError("Groq response was not valid JSON") from exc
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIOutputValidationError(
                "Groq response did not contain recommendation content"
            ) from exc
        if not isinstance(content, str):
            raise AIOutputValidationError("Groq recommendation content was not text")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise AIOutputValidationError("Groq recommendation content was not valid JSON") from exc


class ProviderAdapter:
    """Adapts an SDK-free transport into the RecoveryOS AIProvider contract."""

    def __init__(
        self,
        transport: ProviderTransport,
        *,
        timeout_seconds: float,
        prompt_version: str,
        model_version: str,
        schema_version: str = "recommendation-v1",
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not prompt_version or not model_version or not schema_version:
            raise ValueError("AI version references must be non-empty")
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.prompt_version = prompt_version
        self.model_version = model_version
        self.schema_version = schema_version

    def recommend(self, evidence: RecommendationEvidence) -> RecommendationOutput:
        safe_payload = evidence.model_dump(mode="json")
        executor = ThreadPoolExecutor(max_workers=1)
        future: Future[object] = executor.submit(self.transport, safe_payload)
        try:
            raw = future.result(timeout=self.timeout_seconds)
        except FutureTimeout as exc:
            future.cancel()
            raise AITimeoutError("AI provider timed out") from exc
        except AIProviderError:
            raise
        except Exception as exc:
            raise AITransportError("AI provider request failed") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if isinstance(raw, RecommendationOutput):
            payload = raw.model_dump(mode="python")
        elif isinstance(raw, Mapping):
            payload = dict(raw)
        else:
            raise AIOutputValidationError("AI provider returned an invalid response shape")

        # Provider output cannot choose the versions that are persisted for auditing.
        payload["prompt_version"] = self.prompt_version
        payload["model_version"] = self.model_version
        payload["schema_version"] = self.schema_version
        try:
            return RecommendationOutput.model_validate(payload)
        except ValidationError as exc:
            raise AIOutputValidationError("AI provider returned an invalid recommendation") from exc


class StaticAIProvider:
    """Deterministic test/demo transport; it is not a production accuracy claim."""

    def __init__(self, response: object) -> None:
        self.response = response

    def recommend(self, evidence: RecommendationEvidence) -> RecommendationOutput:
        del evidence
        if isinstance(self.response, RecommendationOutput):
            return self.response
        try:
            return RecommendationOutput.model_validate(self.response)
        except ValidationError as exc:
            raise AIOutputValidationError(
                "static provider returned an invalid recommendation"
            ) from exc
