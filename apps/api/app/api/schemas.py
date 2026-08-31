from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.contracts import ActionType
from app.policy.schema import Channel


class CaseSummaryResponse(BaseModel):
    id: str
    obligation_id: str
    source_type: str
    status: str
    currency: str
    amount_at_risk_minor_units: int
    expected_recoverable_amount_minor_units: int | None
    recovered_amount_minor_units: int
    attribution_status: str
    priority_score: int | None
    incident_suppressed: bool
    created_at: datetime


class TimelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    entity_id: str
    event_type: str
    actor_type: str
    reason: str
    metadata: dict[str, Any]
    correlation_id: str
    created_at: datetime


class CaseDetailResponse(CaseSummaryResponse):
    customer_id: str | None
    root_cause: str | None
    root_cause_confidence: int | None
    recovery_probability: int | None
    recovery_attempt_count: int
    max_attempts: int
    closed_at: datetime | None
    attempts: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    policy_decisions: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    timeline: list[TimelineResponse]


class IncidentResponse(BaseModel):
    id: str
    dimension_key: str
    status: str
    confidence: int
    baseline_window: dict[str, Any]
    current_window: dict[str, Any]
    evidence: dict[str, Any]
    detector_version: str
    opened_at: datetime
    resolved_at: datetime | None
    cooldown_until: datetime | None
    affected_case_ids: list[str]


class DashboardResponse(BaseModel):
    merchant_id: str
    freshness: str
    metrics: dict[str, int | None]


class SimulatorRunRequest(BaseModel):
    seed: int
    transaction_count: int
    amounts_minor_units: list[int]
    payment_methods: list[str]
    failure_codes: list[str]
    high_value_indices: list[int] = Field(default_factory=list)
    high_value_amount_minor_units: int | None = None
    duplicate_event_indices: list[int] = Field(default_factory=list)
    opt_out_indices: list[int] = Field(default_factory=list)
    incident_indices: list[int] = Field(default_factory=list)
    natural_recovery_indices: list[int] = Field(default_factory=list)
    assisted_recovery_indices: list[int] = Field(default_factory=list)
    provider_failure_indices: list[int] = Field(default_factory=list)


class SimulatorRunResponse(BaseModel):
    seed: int
    label: str
    persisted_event_count: int
    duplicate_event_count: int
    case_count: int
    recommendation_count: int
    success_event_count: int
    scenario_counts: dict[str, int]
    event_ids: tuple[str, ...]
    case_ids: tuple[str, ...]


class ActionCommandRequest(BaseModel):
    action_type: ActionType
    idempotency_key: str = Field(min_length=1, max_length=255)
    due_at: datetime
    channel: Channel | None = None
    recommendation_id: str | None = None


class ActionCommandResponse(BaseModel):
    status: str
    case_id: str
    policy_decision_id: str
    job_id: str | None
    reason: str
