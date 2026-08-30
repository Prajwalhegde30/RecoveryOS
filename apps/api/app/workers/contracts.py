from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class WorkItem:
    job_id: str
    action_id: str
    case_id: str
    action_type: str
    action_idempotency_key: str
    policy_version_id: str
    case_status: str


@dataclass(frozen=True)
class PreflightResult:
    allowed: bool
    reason_code: str


@dataclass(frozen=True)
class ActionExecutionResult:
    provider_reference: str | None = None
    cost_minor_units: int = 0

    def __post_init__(self) -> None:
        if self.cost_minor_units < 0:
            raise ValueError("cost_minor_units must be non-negative")


class PreflightChecker(Protocol):
    def check(self, work: WorkItem, *, now: datetime) -> PreflightResult:
        """Return whether the customer-facing action is safe to execute now."""


class ActionExecutor(Protocol):
    def execute(self, work: WorkItem) -> ActionExecutionResult:
        """Execute exactly one provider effect for the supplied action identity."""


class ActionExecutionError(Exception):
    """Safe provider failure that carries retryability without raw provider details."""

    def __init__(self, category: str, safe_message: str, *, retryable: bool) -> None:
        super().__init__(safe_message)
        self.category = category
        self.safe_message = safe_message
        self.retryable = retryable
