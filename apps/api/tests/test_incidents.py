from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.incidents.service import (
    IncidentDetectionStatus,
    IncidentDetectorConfig,
    IncidentDetectorService,
)
from app.incidents.suppression import IncidentSuppressionService
from app.persistence.base import Base
from app.persistence.models import (
    AuditEvent,
    Incident,
    JobStatus,
    Merchant,
    Obligation,
    PaymentAttempt,
    RecoveryAction,
    RecoveryCase,
    RecoveryCaseStatus,
    ScheduledJob,
)

MERCHANT_ID = "merchant-incident"
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def make_session() -> Session:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(
        Merchant(
            id=MERCHANT_ID,
            external_key="incident-merchant",
            name="Incident Merchant",
            default_currency="INR",
            timezone="UTC",
            environment_mode="test",
            status="active",
        )
    )
    session.add(
        Obligation(
            id="obligation-incident",
            merchant_id=MERCHANT_ID,
            obligation_type="payment",
            external_obligation_id="order-incident",
            amount_at_risk=1000,
            currency="INR",
            status="open",
            authoritative_status="outstanding",
        )
    )
    session.add(
        RecoveryCase(
            id="case-incident",
            merchant_id=MERCHANT_ID,
            obligation_id="obligation-incident",
            source_type="payment_failure",
            status=RecoveryCaseStatus.WAITING,
            max_attempts_snapshot=3,
            recovered_amount=0,
            currency="INR",
            attribution_status="unrecovered",
        )
    )
    session.commit()
    return session


def config() -> IncidentDetectorConfig:
    return IncidentDetectorConfig(
        baseline_window=timedelta(minutes=10),
        current_window=timedelta(minutes=5),
        minimum_baseline_attempts=2,
        minimum_current_attempts=2,
        degradation_threshold_percentage_points=20,
        resolution_threshold_percentage_points=5,
        cooldown=timedelta(minutes=10),
    )


def add_attempts(
    session: Session, *, prefix: str, at: datetime, failed: int, total: int = 4
) -> None:
    for index in range(total):
        session.add(
            PaymentAttempt(
                merchant_id=MERCHANT_ID,
                recovery_case_id="case-incident",
                external_payment_id=f"{prefix}-{index}",
                payment_method="upi",
                provider="simulator",
                amount=1000,
                currency="INR",
                status="failed" if index < failed else "succeeded",
                failure_code="UPI_TIMEOUT" if index < failed else None,
                provider_event_at=at,
            )
        )
    session.commit()


def test_detector_opens_updates_resolves_and_respects_cooldown() -> None:
    session = make_session()
    add_attempts(
        session,
        prefix="baseline",
        at=datetime(2026, 1, 1, 11, 50),
        failed=1,
    )
    add_attempts(
        session,
        prefix="degraded",
        at=datetime(2026, 1, 1, 11, 58),
        failed=3,
    )
    detector = IncidentDetectorService(session, MERCHANT_ID, config())

    opened = detector.detect(now=NOW)
    assert opened.status == IncidentDetectionStatus.OPENED
    assert opened.current_failure_rate_percent == 75
    assert session.scalar(select(func.count(Incident.id))) == 1

    active = detector.detect(now=NOW + timedelta(minutes=1))
    assert active.status == IncidentDetectionStatus.ACTIVE
    assert active.incident_id == opened.incident_id
    assert session.scalar(select(func.count(Incident.id))) == 1

    add_attempts(
        session,
        prefix="recovered",
        at=datetime(2026, 1, 1, 12, 5),
        failed=0,
    )
    resolved = detector.detect(now=NOW + timedelta(minutes=10))
    assert resolved.status == IncidentDetectionStatus.RESOLVED
    assert resolved.incident_id == opened.incident_id

    cooldown = detector.detect(now=NOW + timedelta(minutes=15))
    assert cooldown.status == IncidentDetectionStatus.COOLDOWN
    assert session.scalar(select(func.count(Incident.id))) == 1

    session.close()


def test_detector_requires_samples_and_does_not_mutate_financial_domain() -> None:
    session = make_session()
    add_attempts(
        session,
        prefix="small-baseline",
        at=datetime(2026, 1, 1, 11, 50),
        failed=1,
        total=1,
    )
    add_attempts(
        session,
        prefix="small-current",
        at=datetime(2026, 1, 1, 11, 58),
        failed=1,
        total=1,
    )
    result = IncidentDetectorService(session, MERCHANT_ID, config()).detect(now=NOW)

    assert result.status == IncidentDetectionStatus.NO_INCIDENT
    assert session.scalar(select(func.count(Incident.id))) == 0
    case = session.get(RecoveryCase, "case-incident")
    obligation = session.get(Obligation, "obligation-incident")
    assert case is not None and case.status == RecoveryCaseStatus.WAITING
    assert obligation is not None and obligation.authoritative_status == "outstanding"
    assert session.scalar(select(func.count(AuditEvent.id))) == 0
    session.close()


def test_suppression_associates_cases_cancels_future_jobs_and_releases_after_cooldown() -> None:
    session = make_session()
    add_attempts(
        session,
        prefix="baseline-suppression",
        at=datetime(2026, 1, 1, 11, 50),
        failed=1,
    )
    add_attempts(
        session,
        prefix="current-suppression",
        at=datetime(2026, 1, 1, 11, 58),
        failed=3,
    )
    incident = IncidentDetectorService(session, MERCHANT_ID, config()).detect(now=NOW)
    assert incident.incident_id is not None

    session.add_all(
        [
            RecoveryAction(
                id="action-pending-incident",
                merchant_id=MERCHANT_ID,
                recovery_case_id="case-incident",
                action_type="send_retry_link",
                status="SCHEDULED",
                idempotency_key="incident-pending-action",
                cost_minor_units=0,
                correlation_id="test",
            ),
            RecoveryAction(
                id="action-claimed-incident",
                merchant_id=MERCHANT_ID,
                recovery_case_id="case-incident",
                action_type="send_retry_link",
                status="EXECUTING",
                idempotency_key="incident-claimed-action",
                cost_minor_units=0,
                correlation_id="test",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            ScheduledJob(
                id="job-pending-incident",
                merchant_id=MERCHANT_ID,
                recovery_case_id="case-incident",
                recovery_action_id="action-pending-incident",
                job_type="recovery_action",
                status=JobStatus.PENDING,
                due_at=datetime(2026, 1, 1, 13),
                attempt_count=0,
                max_attempts=3,
                idempotency_key="incident-pending-job",
                correlation_id="test",
            ),
            ScheduledJob(
                id="job-claimed-incident",
                merchant_id=MERCHANT_ID,
                recovery_case_id="case-incident",
                recovery_action_id="action-claimed-incident",
                job_type="recovery_action",
                status=JobStatus.CLAIMED,
                due_at=datetime(2026, 1, 1, 11, 59),
                attempt_count=1,
                max_attempts=3,
                lease_until=datetime(2026, 1, 1, 12, 1),
                idempotency_key="incident-claimed-job",
                correlation_id="test",
            ),
        ]
    )
    session.commit()

    service = IncidentSuppressionService(session, MERCHANT_ID)
    result = service.suppress(incident.incident_id)
    assert result.associated_case_count == 1
    assert result.suppressed_case_count == 1
    assert result.cancelled_job_count == 1
    assert result.preserved_active_job_count == 1
    session.rollback()
    case = session.get(RecoveryCase, "case-incident")
    pending = session.get(ScheduledJob, "job-pending-incident")
    claimed = session.get(ScheduledJob, "job-claimed-incident")
    assert case is not None and case.status == RecoveryCaseStatus.SUPPRESSED
    assert pending is not None and pending.status == JobStatus.CANCELLED
    assert claimed is not None and claimed.status == JobStatus.CLAIMED

    stored_incident = session.get(Incident, incident.incident_id)
    assert stored_incident is not None
    stored_incident.status = "RESOLVED"
    stored_incident.cooldown_until = NOW + timedelta(minutes=10)
    session.commit()
    release = service.release_after_cooldown(
        incident.incident_id,
        now=NOW + timedelta(minutes=20),
    )
    assert release.released_case_count == 1
    session.rollback()
    case = session.get(RecoveryCase, "case-incident")
    assert case is not None and case.status == RecoveryCaseStatus.WAITING
    assert case.incident_suppressed is False
    session.close()
