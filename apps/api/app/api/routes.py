from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.actions.service import ActionCommandService
from app.api.dependencies import (
    admin_dependency,
    get_db_session,
    get_merchant_scope,
    operator_dependency,
)
from app.api.schemas import (
    ActionCommandRequest,
    ActionCommandResponse,
    CaseDetailResponse,
    CaseSummaryResponse,
    ComponentHealthResponse,
    CurrentPolicyResponse,
    DashboardResponse,
    IncidentResponse,
    OperationalHealthResponse,
    SimulatorRunRequest,
    SimulatorRunResponse,
    TimelineResponse,
)
from app.attribution.metrics import RecoveryMetricsService
from app.auth.service import AuthContext
from app.config import get_settings
from app.integrations.simulated import SimulatedMessagingProvider, SimulatedPaymentProvider
from app.jobs.service import JobConfig
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
    ScheduledJob,
)
from app.policy.service import PolicyService
from app.simulator.lifecycle import SimulatorLifecycleResult, SimulatorLifecycleService
from app.simulator.service import SimulatorConfig

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


@router.get("/health/operational", response_model=OperationalHealthResponse)
def operational_health(
    merchant_id: str = merchant_scope_dependency,
    session: Session = db_session_dependency,
) -> OperationalHealthResponse:
    """Expose safe tenant-scoped signals without claiming worker heartbeats."""

    now = datetime.now(UTC).replace(tzinfo=None)
    pending_jobs = int(
        session.scalar(
            select(func.count())
            .select_from(ScheduledJob)
            .where(ScheduledJob.merchant_id == merchant_id, ScheduledJob.status == "PENDING")
        )
        or 0
    )
    stale_claims = int(
        session.scalar(
            select(func.count())
            .select_from(ScheduledJob)
            .where(
                ScheduledJob.merchant_id == merchant_id,
                ScheduledJob.status == "CLAIMED",
                ScheduledJob.lease_until < now,
            )
        )
        or 0
    )
    payment_health = SimulatedPaymentProvider().health()
    messaging_health = SimulatedMessagingProvider().health()
    return OperationalHealthResponse(
        merchant_id=merchant_id,
        checked_at=datetime.now(UTC),
        components={
            "database": ComponentHealthResponse(status="healthy", detail="tenant query succeeded"),
            "worker": ComponentHealthResponse(
                status="degraded" if stale_claims else "unknown",
                detail=(
                    "claimed jobs have expired leases"
                    if stale_claims
                    else "worker heartbeat is not registered in this API process"
                ),
                pending_jobs=pending_jobs,
                stale_claims=stale_claims,
            ),
            payment_health.provider: ComponentHealthResponse(
                status=payment_health.status.value, detail=payment_health.detail
            ),
            messaging_health.provider: ComponentHealthResponse(
                status=messaging_health.status.value, detail=messaging_health.detail
            ),
        },
    )


@router.get("/policies/current", response_model=CurrentPolicyResponse)
def current_policy(
    merchant_id: str = merchant_scope_dependency,
    session: Session = db_session_dependency,
) -> CurrentPolicyResponse:
    session.rollback()
    active = PolicyService(session, merchant_id).active()
    if active is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="active policy not found")
    version, policy = active
    version_number = version.version
    version_status = version.status
    policy_document = policy.model_dump(mode="json")
    session.rollback()
    return CurrentPolicyResponse(
        version=version_number,
        status=version_status,
        policy=policy_document,
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


@router.post("/cases/{case_id}/actions", response_model=ActionCommandResponse)
def request_action(
    case_id: str,
    request: ActionCommandRequest,
    _operator: AuthContext = operator_dependency,
    merchant_id: str = merchant_scope_dependency,
    session: Session = db_session_dependency,
) -> ActionCommandResponse:
    settings = get_settings()
    try:
        result = ActionCommandService(
            session,
            merchant_id,
            JobConfig(
                max_attempts=settings.max_recovery_attempts,
                lease_seconds=settings.job_lease_seconds,
                backoff_base_seconds=settings.job_backoff_base_seconds,
                backoff_max_seconds=settings.job_backoff_max_seconds,
            ),
        ).request(
            case_id=case_id,
            action_type=request.action_type,
            idempotency_key=request.idempotency_key,
            due_at=request.due_at,
            actor_id=_operator.subject,
            channel=request.channel,
            recommendation_id=request.recommendation_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ActionCommandResponse(
        status=result.status,
        case_id=result.case_id,
        policy_decision_id=result.policy_decision_id,
        job_id=result.job_id,
        reason=result.reason,
    )


@router.post("/simulator/runs", response_model=SimulatorRunResponse)
def run_simulator(
    request: SimulatorRunRequest,
    _admin: AuthContext = admin_dependency,
    merchant_id: str = merchant_scope_dependency,
    session: Session = db_session_dependency,
) -> SimulatorRunResponse:
    # The simulator owns its application-service transactions; lifecycle state is
    # persisted before/after the generated facts and is never a source of money.
    session.rollback()
    config = SimulatorConfig(
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
    )
    try:
        lifecycle = SimulatorLifecycleService(session, merchant_id)
        run = lifecycle.start(
            config,
            run_key=request.run_key or f"seed:{request.seed}",
            actor_id=_admin.subject,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _simulator_response(run)


@router.get("/simulator/runs/{run_id}", response_model=SimulatorRunResponse)
def simulator_run_status(
    run_id: str,
    _admin: AuthContext = admin_dependency,
    merchant_id: str = merchant_scope_dependency,
    session: Session = db_session_dependency,
) -> SimulatorRunResponse:
    try:
        return _simulator_response(SimulatorLifecycleService(session, merchant_id).get(run_id))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/simulator/runs/{run_id}/reset", response_model=SimulatorRunResponse)
def reset_simulator_run(
    run_id: str,
    _admin: AuthContext = admin_dependency,
    merchant_id: str = merchant_scope_dependency,
    session: Session = db_session_dependency,
) -> SimulatorRunResponse:
    try:
        result = SimulatorLifecycleService(session, merchant_id).reset(
            run_id, actor_id=_admin.subject, correlation_id="simulator-reset"
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _simulator_response(result)


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


def _simulator_response(result: SimulatorLifecycleResult) -> SimulatorRunResponse:
    run = result.result
    return SimulatorRunResponse(
        run_id=result.run_id,
        status=result.status,
        seed=run.seed if run else 0,
        label=run.label if run else "synthetic_simulator_data",
        persisted_event_count=run.persisted_event_count if run else None,
        duplicate_event_count=run.duplicate_event_count if run else None,
        case_count=run.case_count if run else None,
        recommendation_count=run.recommendation_count if run else None,
        success_event_count=run.success_event_count if run else None,
        scenario_counts=run.scenario_counts if run else None,
        event_ids=run.event_ids if run else (),
        case_ids=run.case_ids if run else (),
        error_safe=result.error_safe,
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
