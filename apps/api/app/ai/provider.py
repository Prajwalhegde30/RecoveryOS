from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any, Protocol

from pydantic import ValidationError

from app.ai.contracts import RecommendationEvidence, RecommendationOutput


class AIProviderError(Exception):
    """Base error for failures at the AI provider boundary."""


class AITimeoutError(AIProviderError):
    """The provider did not return within the configured timeout."""


class AIOutputValidationError(AIProviderError):
    """The provider response was not a safe recommendation contract."""


class AITransportError(AIProviderError):
    """The provider transport failed without exposing provider details."""


class AIProvider(Protocol):
    def recommend(self, evidence: RecommendationEvidence) -> RecommendationOutput:
        """Return a validated proposal or raise a typed provider error."""


ProviderTransport = Callable[[dict[str, Any]], object]


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
