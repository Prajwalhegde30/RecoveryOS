from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import admin_dependency, get_db_session, get_merchant_scope
from app.api.schemas import (
    CaseDetailResponse,
    CaseSummaryResponse,
    DashboardResponse,
    IncidentResponse,
    SimulatorRunRequest,
    SimulatorRunResponse,
    TimelineResponse,
)
from app.attribution.metrics import RecoveryMetricsService
from app.auth.service import AuthContext
from app.persistence.models import (
    AuditEvent,
    CaseIncident,
    Incident,
    Obligation,
    PaymentAttempt,
    PolicyDecision,
    Recommendation,
    RecoveryAction,
    RecoveryCase,
)
from app.simulator.service import SimulatorConfig, SimulatorService

router = APIRouter(prefix="/api/v1", tags=["recovery"])
db_session_dependency = Depends(get_db_session)
merchant_scope_dependency = Depends(get_merchant_scope)


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    merchant_id: str = merchant_scope_dependency,
    session: Session = db_session_dependency,
) -> DashboardResponse:
    metrics = RecoveryMetricsService(session, merchant_id).calculate()
    return DashboardResponse(
        merchant_id=merchant_id,
        freshness="live",
        metrics={
            "revenue_at_risk_minor_units": metrics.revenue_at_risk_minor_units,
            "expected_recoverable_minor_units": metrics.expected_recoverable_minor_units,
            "recovered_minor_units": metrics.recovered_minor_units,
            "natural_recovered_minor_units": metrics.natural_recovered_minor_units,
            "assisted_recovered_minor_units": metrics.assisted_recovered_minor_units,
            "suppressed_minor_units": metrics.suppressed_minor_units,
            "unrecovered_minor_units": metrics.unrecovered_minor_units,
            "recovery_cost_minor_units": metrics.recovery_cost_minor_units,
            "net_recovery_minor_units": metrics.net_recovery_minor_units,
            "recovered_case_count": metrics.recovered_case_count,
            "recovery_rate_percent": metrics.recovery_rate_percent,
            "median_time_to_recovery_seconds": metrics.median_time_to_recovery_seconds,
        },
    )


@router.get("/cases", response_model=list[CaseSummaryResponse])
def cases(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    merchant_id: str = merchant_scope_dependency,
    session: Session = db_session_dependency,
) -> list[CaseSummaryResponse]:
    statement = (
        select(RecoveryCase, Obligation)
        .join(Obligation, Obligation.id == RecoveryCase.obligation_id)
        .where(RecoveryCase.merchant_id == merchant_id)
        .order_by(RecoveryCase.created_at.desc(), RecoveryCase.id.asc())
        .offset(offset)
        .limit(limit)
    )
    if status_filter is not None:
        statement = statement.where(RecoveryCase.status == status_filter)
    return [_summary(case, obligation) for case, obligation in session.execute(statement).all()]


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
def case_detail(
    case_id: str,
    merchant_id: str = merchant_scope_dependency,
    session: Session = db_session_dependency,
) -> CaseDetailResponse:
    row = session.execute(
        select(RecoveryCase, Obligation)
        .join(Obligation, Obligation.id == RecoveryCase.obligation_id)
        .where(RecoveryCase.id == case_id, RecoveryCase.merchant_id == merchant_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
    case, obligation = row
    attempts = list(
        session.scalars(
            select(PaymentAttempt).where(
                PaymentAttempt.recovery_case_id == case_id,
                PaymentAttempt.merchant_id == merchant_id,
            )
        )
    )
    recommendations = _safe_rows(
        session.scalars(
            select(Recommendation).where(
                Recommendation.recovery_case_id == case_id,
                Recommendation.merchant_id == merchant_id,
            )
        ),
        {"evidence_json"},
    )
    decisions = _safe_rows(
        session.scalars(
            select(PolicyDecision).where(
                PolicyDecision.recovery_case_id == case_id,
                PolicyDecision.merchant_id == merchant_id,
            )
        ),
        {"input_snapshot_json"},
    )
    actions = _safe_rows(
        session.scalars(
            select(RecoveryAction).where(
                RecoveryAction.recovery_case_id == case_id,
                RecoveryAction.merchant_id == merchant_id,
            )
        ),
        set(),
    )
    audit = list(
        session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.entity_id == case_id,
                AuditEvent.merchant_id == merchant_id,
            )
            .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
        )
    )
    return CaseDetailResponse(
        **_summary(case, obligation).model_dump(),
        customer_id=case.customer_id,
        root_cause=case.root_cause,
        root_cause_confidence=case.root_cause_confidence,
        recovery_probability=case.recovery_probability,
        recovery_attempt_count=case.attempt_count,
        max_attempts=case.max_attempts_snapshot,
        closed_at=case.closed_at,
        attempts=_safe_rows(attempts, set()),
        recommendations=recommendations,
        policy_decisions=decisions,
        actions=actions,
        timeline=[
            TimelineResponse(
                id=event.id,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                event_type=event.event_type,
                actor_type=event.actor_type,
                reason=event.reason,
                metadata=event.metadata_safe_json,
                correlation_id=event.correlation_id,
                created_at=event.created_at,
            )
            for event in audit
        ],
    )


@router.get("/incidents", response_model=list[IncidentResponse])
def incidents(
    active_only: bool = Query(default=False),
    merchant_id: str = merchant_scope_dependency,
    session: Session = db_session_dependency,
) -> list[IncidentResponse]:
    statement = select(Incident).where(Incident.merchant_id == merchant_id)
    if active_only:
        statement = statement.where(Incident.status == "OPEN")
    records = session.scalars(statement.order_by(Incident.opened_at.desc())).all()
    responses: list[IncidentResponse] = []
    for incident in records:
        case_ids = list(
            session.scalars(
                select(CaseIncident.recovery_case_id).where(CaseIncident.incident_id == incident.id)
            )
        )
        responses.append(
            IncidentResponse(
                id=incident.id,
                dimension_key=incident.dimension_key,
                status=incident.status,
                confidence=incident.confidence,
                baseline_window=incident.baseline_window,
                current_window=incident.current_window,
                evidence=incident.evidence_json,
                detector_version=incident.detector_version,
                opened_at=incident.opened_at,
                resolved_at=incident.resolved_at,
                cooldown_until=incident.cooldown_until,
                affected_case_ids=case_ids,
            )
        )
    return responses


@router.post("/simulator/runs", response_model=SimulatorRunResponse)
def run_simulator(
    request: SimulatorRunRequest,
    _admin: AuthContext = admin_dependency,
    merchant_id: str = merchant_scope_dependency,
    session: Session = db_session_dependency,
) -> SimulatorRunResponse:
    # The simulator owns its application-service transactions; discard any read
    # transaction opened by a prior request on a reused test/session boundary.
    session.rollback()
    try:
        result = SimulatorService(
            session,
            SimulatorConfig(
                seed=request.seed,
                merchant_ids=(merchant_id,),
                transaction_count=request.transaction_count,
                amounts_minor_units=tuple(request.amounts_minor_units),
                payment_methods=tuple(request.payment_methods),
                failure_codes=tuple(request.failure_codes),
                high_value_indices=frozenset(request.high_value_indices),
                high_value_amount_minor_units=request.high_value_amount_minor_units,
                duplicate_event_indices=frozenset(request.duplicate_event_indices),
                opt_out_indices=frozenset(request.opt_out_indices),
                incident_indices=frozenset(request.incident_indices),
                natural_recovery_indices=frozenset(request.natural_recovery_indices),
                assisted_recovery_indices=frozenset(request.assisted_recovery_indices),
                provider_failure_indices=frozenset(request.provider_failure_indices),
            ),
        ).run()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return SimulatorRunResponse(
        seed=result.seed,
        label=result.label,
        persisted_event_count=result.persisted_event_count,
        duplicate_event_count=result.duplicate_event_count,
        case_count=result.case_count,
        recommendation_count=result.recommendation_count,
        success_event_count=result.success_event_count,
        scenario_counts=result.scenario_counts,
        event_ids=result.event_ids,
        case_ids=result.case_ids,
    )


def _summary(case: RecoveryCase, obligation: Obligation) -> CaseSummaryResponse:
    return CaseSummaryResponse(
        id=case.id,
        obligation_id=case.obligation_id,
        source_type=case.source_type,
        status=case.status,
        currency=case.currency,
        amount_at_risk_minor_units=obligation.amount_at_risk,
        expected_recoverable_amount_minor_units=case.expected_recoverable_amount,
        recovered_amount_minor_units=case.recovered_amount,
        attribution_status=case.attribution_status,
        priority_score=case.priority_score,
        incident_suppressed=case.incident_suppressed,
        created_at=case.created_at,
    )


def _safe_rows(rows: Iterable[Any], json_columns: set[str]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for row in rows:
        values: dict[str, object] = {}
        for key, value in row.__dict__.items():
            if key.startswith("_") or key in json_columns:
                continue
            if key in {"provider_reference", "failure_detail_safe"}:
                values[key] = value
            elif key not in {"normalized_payload", "metadata_safe_json"}:
                values[key] = value
        result.append(values)
    return result
