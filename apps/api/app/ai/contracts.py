from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActionType(StrEnum):
    NO_ACTION = "NO_ACTION"
    WAIT = "WAIT"
    RETRY = "RETRY"
    GENERATE_PAYMENT_LINK = "GENERATE_PAYMENT_LINK"
    SEND_EMAIL = "SEND_EMAIL"
    SEND_SMS = "SEND_SMS"
    SEND_WHATSAPP = "SEND_WHATSAPP"
    SUGGEST_ALTERNATE_PAYMENT_METHOD = "SUGGEST_ALTERNATE_PAYMENT_METHOD"
    REQUEST_PAYMENT_METHOD_UPDATE = "REQUEST_PAYMENT_METHOD_UPDATE"
    SCHEDULE_RETRY = "SCHEDULE_RETRY"
    NOTIFY_ACCOUNT_MANAGER = "NOTIFY_ACCOUNT_MANAGER"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"
    STOP = "STOP"
    CLOSE_CASE = "CLOSE_CASE"


class RecommendationSource(StrEnum):
    AI = "AI"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"
    RULE = "RULE"


class RecommendationEvidence(BaseModel):
    """Minimized, non-PII evidence allowed to cross the AI provider boundary."""

    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(min_length=1, max_length=64)
    root_cause: str = Field(min_length=1, max_length=128)
    root_cause_confidence_percent: int = Field(ge=0, le=100)
    recovery_probability_percent: int = Field(ge=0, le=100)
    expected_recoverable_amount_minor_units: int = Field(ge=0)
    priority_score: int = Field(ge=0)
    payment_method: str | None = Field(default=None, max_length=64)
    failure_code: str | None = Field(default=None, max_length=128)
    attempt_count: int = Field(ge=0)
    incident_active: bool = False
    evidence_conflict: bool = False
    scoring_version: str = Field(min_length=1, max_length=64)


_ACTION_PARAMETER_KEYS: dict[ActionType, frozenset[str]] = {
    ActionType.WAIT: frozenset({"delay_minutes"}),
    ActionType.SCHEDULE_RETRY: frozenset({"delay_minutes"}),
    ActionType.SUGGEST_ALTERNATE_PAYMENT_METHOD: frozenset({"alternate_payment_method"}),
}

_FORBIDDEN_PARAMETER_KEYS = frozenset(
    {
        "amount",
        "amount_minor_units",
        "authorization",
        "command",
        "currency",
        "payment_amount",
        "recipient",
        "tool",
        "url",
    }
)


class RecommendationOutput(BaseModel):
    """Validated proposal returned by an AI adapter, never an execution command."""

    model_config = ConfigDict(extra="forbid")

    action: ActionType
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason_code: str = Field(min_length=1, max_length=128)
    rationale: str = Field(min_length=1, max_length=4000)
    evidence: list[str] = Field(min_length=1, max_length=32)
    confidence_percent: int = Field(ge=0, le=100)
    fallback_action: ActionType
    prompt_version: str = Field(min_length=1, max_length=64)
    model_version: str = Field(min_length=1, max_length=128)
    schema_version: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_parameters(self) -> "RecommendationOutput":
        allowed = _ACTION_PARAMETER_KEYS.get(self.action, frozenset())
        supplied = frozenset(self.parameters)
        forbidden = supplied & _FORBIDDEN_PARAMETER_KEYS
        if forbidden:
            raise ValueError("recommendation contains forbidden parameter keys")
        if not supplied <= allowed:
            raise ValueError("recommendation contains unsupported action parameters")

        if "delay_minutes" in self.parameters:
            delay = self.parameters["delay_minutes"]
            if isinstance(delay, bool) or not isinstance(delay, int) or delay < 0:
                raise ValueError("delay_minutes must be a non-negative integer")
        if "alternate_payment_method" in self.parameters:
            method = self.parameters["alternate_payment_method"]
            if not isinstance(method, str) or not method.strip():
                raise ValueError("alternate_payment_method must be a non-empty string")
        return self
