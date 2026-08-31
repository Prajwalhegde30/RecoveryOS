from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


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
