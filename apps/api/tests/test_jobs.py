from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.jobs.service import JobConfig, JobService
from app.persistence.base import Base
from app.persistence.models import (
    AuditEvent,
    JobStatus,
    Obligation,
    PolicyDecision,
    PolicyVersion,
    RecoveryAction,
    RecoveryCase,
    RecoveryCaseStatus,
    ScheduledJob,
)


def config(max_attempts: int = 2) -> JobConfig:
    return JobConfig(
        max_attempts=max_attempts,
        lease_seconds=30,
        backoff_base_seconds=10,
        backoff_max_seconds=60,
    )


def setup_context(session: Session, merchant_id: str = "merchant_jobs") -> tuple[str, str, str]:
    obligation = Obligation(
        merchant_id=merchant_id,
        obligation_type="payment",
        external_obligation_id=f"order-{merchant_id}",
        amount_at_risk=10_000,
        currency="INR",
        status="open",
        authoritative_status="unpaid",
    )
    session.add(obligation)
    session.flush()
    case = RecoveryCase(
        merchant_id=merchant_id,
        obligation_id=obligation.id,
        source_type="payment.failed",
        status=RecoveryCaseStatus.POLICY_CHECK,
        attempt_count=0,
        max_attempts_snapshot=3,
        recovered_amount=0,
        currency="INR",
        attribution_status="pending",
    )
    session.add(case)
    session.flush()
    version = PolicyVersion(
        merchant_id=merchant_id,
        version=1,
        policy_json={},
        created_by="admin-1",
        status="ACTIVE",
    )
    session.add(version)
    session.flush()
    decision = PolicyDecision(
        merchant_id=merchant_id,
        recovery_case_id=case.id,
        policy_version_id=version.id,
        result="SCHEDULE",
        decisive_rule="MINIMUM_CONTACT_INTERVAL",
        reason="policy requires scheduled execution",
        input_snapshot_json={},
        actor_type="system",
        correlation_id="policy-test",
    )
    session.add(decision)
    session.flush()
    case_id = case.id
    decision_id = decision.id
    version_id = version.id
    session.commit()
    return case_id, decision_id, version_id


def schedule(
    session: Session,
    *,
    max_attempts: int = 2,
    merchant_id: str = "merchant_jobs",
    idempotency_key: str = "action-1",
) -> tuple[JobService, str, str, str, str]:
    case_id, decision_id, version_id = setup_context(session, merchant_id)
    service = JobService(session, merchant_id, config(max_attempts))
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    job = service.schedule_action(
        case_id=case_id,
        policy_decision_id=decision_id,
        policy_version_id=version_id,
        action_type="SEND_EMAIL",
        idempotency_key=idempotency_key,
        due_at=now,
        channel="email",
    )
    job_id = job.id
    session.rollback()
    return service, job_id, case_id, decision_id, version_id


def test_job_creation_is_idempotent_and_traced_to_policy() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service, job_id, case_id, decision_id, version_id = schedule(session)
        session.rollback()
        same = service.schedule_action(
            case_id=case_id,
            policy_decision_id=decision_id,
            policy_version_id=version_id,
            action_type="SEND_EMAIL",
            idempotency_key="action-1",
            due_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
            channel="email",
        )
        assert same.id == job_id
        session.rollback()
        jobs = session.scalars(select(ScheduledJob)).all()
        actions = session.scalars(select(RecoveryAction)).all()
        assert len(jobs) == 1
        assert len(actions) == 1
        assert jobs[0].policy_version_id == version_id
        assert actions[0].policy_version_id == version_id
        assert session.scalar(select(AuditEvent).where(AuditEvent.event_type == "ACTION_SCHEDULED"))


def test_claim_retry_and_terminal_failure_are_bounded() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service, job_id, _, _, _ = schedule(session, max_attempts=2)
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        claimed = service.claim_due(now=now)
        assert claimed is not None
        assert claimed.id == job_id
        assert claimed.attempt_count == 1
        session.rollback()
        assert service.claim_due(now=now) is None
        session.rollback()

        retried = service.retry_or_fail(
            job_id,
            now=now,
            error_category="provider_timeout",
            error_safe="provider did not respond",
        )
        assert retried.status == JobStatus.PENDING
        retry_at = retried.next_retry_at
        assert retry_at is not None
        session.rollback()
        claimed_again = service.claim_due(now=retry_at.replace(tzinfo=UTC))
        assert claimed_again is not None
        session.rollback()
        failed = service.retry_or_fail(
            job_id,
            now=retry_at.replace(tzinfo=UTC),
            error_category="provider_timeout",
            error_safe="provider did not respond again",
        )
        assert failed.status == JobStatus.FAILED
        session.rollback()
        action = session.scalar(select(RecoveryAction))
        assert action is not None
        assert action.status == "FAILED"


def test_job_completion_persists_injected_execution_time() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service, job_id, _, _, _ = schedule(session, max_attempts=2)
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        claimed = service.claim_due(now=now)
        assert claimed is not None
        executed_at = now + timedelta(minutes=3)
        service.complete(job_id, provider_reference="provider-1", executed_at=executed_at)
        session.rollback()
        action = session.scalar(
            select(RecoveryAction).where(RecoveryAction.id == claimed.recovery_action_id)
        )
        assert action is not None
        assert action.executed_at == executed_at.replace(tzinfo=None)


def test_cancel_and_expired_lease_recovery_are_safe() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service, job_id, _, _, _ = schedule(session)
        cancelled = service.cancel(job_id, reason="payment succeeded before execution")
        assert cancelled.status == JobStatus.CANCELLED
        session.rollback()
        assert service.cancel(job_id, reason="duplicate cancellation").status == JobStatus.CANCELLED
        session.rollback()

        service, job_id, _, _, _ = schedule(
            session, merchant_id="merchant_jobs_lease", idempotency_key="action-lease"
        )
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        assert service.claim_due(now=now) is not None
        session.rollback()
        assert service.recover_expired_leases(now=now + timedelta(seconds=31)) == 1
        session.rollback()
        recovered = session.get(ScheduledJob, job_id)
        assert recovered is not None
        assert recovered.status == JobStatus.PENDING


def test_job_config_and_policy_scope_are_validated() -> None:
    with pytest.raises(ValueError, match="positive"):
        JobConfig(0, 30, 10, 60)
    with pytest.raises(ValueError, match="at least"):
        JobConfig(2, 30, 60, 10)

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _, job_id, _, _, _ = schedule(session)
        session.rollback()
        with pytest.raises(LookupError, match="not found"):
            JobService(session, "other_merchant", config()).cancel(
                job_id, reason="cross tenant attempt"
            )
