from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.contracts import ActionType
from app.events.contracts import RevenueEventType
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
    last_updated_at: datetime
    metrics: dict[str, int | None]


class ComponentHealthResponse(BaseModel):
    status: str
    detail: str
    pending_jobs: int | None = None
    stale_claims: int | None = None


class OperationalHealthResponse(BaseModel):
    merchant_id: str
    checked_at: datetime
    components: dict[str, ComponentHealthResponse]


class OperationalMetricsResponse(BaseModel):
    merchant_id: str
    metrics: dict[str, int]


class CurrentPolicyResponse(BaseModel):
    version: int
    status: str
    policy: dict[str, Any]


class ApprovalQueueItemResponse(BaseModel):
    case_id: str
    decision_id: str
    policy_version_id: str
    amount_at_risk_minor_units: int
    currency: str
    reason: str
    created_at: datetime


class SimulatorRunRequest(BaseModel):
    seed: int
    run_key: str | None = Field(default=None, min_length=1, max_length=255)
    transaction_count: int
    amounts_minor_units: list[int]
    payment_methods: list[str]
    failure_codes: list[str]
    event_types: list[RevenueEventType] = Field(default_factory=list)
    high_value_indices: list[int] = Field(default_factory=list)
    high_value_amount_minor_units: int | None = None
    duplicate_event_indices: list[int] = Field(default_factory=list)
    opt_out_indices: list[int] = Field(default_factory=list)
    incident_indices: list[int] = Field(default_factory=list)
    natural_recovery_indices: list[int] = Field(default_factory=list)
    assisted_recovery_indices: list[int] = Field(default_factory=list)
    provider_failure_indices: list[int] = Field(default_factory=list)
    attribution_window_seconds: int = Field(default=3_600, gt=0)


class SimulatorRunResponse(BaseModel):
    run_id: str
    status: str
    seed: int
    label: str
    persisted_event_count: int | None = None
    duplicate_event_count: int | None = None
    case_count: int | None = None
    recommendation_count: int | None = None
    success_event_count: int | None = None
    scenario_counts: dict[str, int] | None = None
    event_ids: tuple[str, ...] = ()
    case_ids: tuple[str, ...] = ()
    error_safe: str | None = None


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


class ApprovalResolutionRequest(BaseModel):
    policy_version_id: str = Field(min_length=1, max_length=36)
    approved: bool
    reason: str = Field(min_length=1, max_length=512)


class ApprovalResolutionResponse(BaseModel):
    decision_id: str
    case_id: str
    status: str
    reason: str
