from datetime import UTC, datetime
from threading import Event

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.events.contracts import RevenueEvent, RevenueEventType
from app.events.service import EventIngestionService
from app.integrations.contracts import PaymentStatus
from app.integrations.simulated import SimulatedPaymentProvider
from app.jobs.service import JobConfig, JobService
from app.persistence.base import Base
from app.persistence.models import (
    Obligation,
    PaymentAttempt,
    PolicyDecision,
    PolicyVersion,
    RecoveryAction,
    RecoveryCase,
    RecoveryCaseStatus,
    ScheduledJob,
)
from app.reconciliation.service import PaymentReconciliationService
from app.workers.contracts import (
    ActionExecutionError,
    ActionExecutionResult,
    PreflightResult,
    WorkItem,
)
from app.workers.service import ProviderPreflightChecker, WorkerService


class FakeExecutor:
    def __init__(self, failure: ActionExecutionError | None = None) -> None:
        self.calls: list[str] = []
        self.failure = failure

    def execute(self, work: WorkItem) -> ActionExecutionResult:
        self.calls.append(work.action_idempotency_key)
        if self.failure is not None:
            failure = self.failure
            self.failure = None
            raise failure
        return ActionExecutionResult(provider_reference="provider-1", cost_minor_units=25)


class FakePreflight:
    def __init__(self, results: list[PreflightResult]) -> None:
        self.results = results

    def check(self, work: WorkItem, *, now: datetime) -> PreflightResult:
        del work, now
        return self.results.pop(0) if self.results else PreflightResult(True, "PREFLIGHT_PASSED")


def setup_job(session: Session, merchant_id: str = "merchant_worker") -> tuple[JobService, str]:
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
        result="ALLOW",
        decisive_rule="NORMAL_POLICY",
        reason="approved for worker test",
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
    service = JobService(
        session,
        merchant_id,
        JobConfig(
            max_attempts=2, lease_seconds=30, backoff_base_seconds=10, backoff_max_seconds=60
        ),
    )
    job = service.schedule_action(
        case_id=case_id,
        policy_decision_id=decision_id,
        policy_version_id=version_id,
        action_type="SEND_EMAIL",
        idempotency_key="worker-action-1",
        due_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
        channel="email",
    )
    job_id = job.id
    session.rollback()
    return service, job_id


def test_worker_success_records_provider_effect_and_case_progression() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        jobs, job_id = setup_job(session)
        executor = FakeExecutor()
        worker = WorkerService(session, "merchant_worker", jobs, executor)
        result = worker.process_once(now=datetime(2026, 1, 1, 12, tzinfo=UTC))
        assert result.status == "succeeded"
        assert result.job_id == job_id
        assert executor.calls == ["worker-action-1"]
        session.rollback()
        job = session.get(ScheduledJob, job_id)
        action = session.scalar(select(RecoveryAction))
        case = session.scalar(select(RecoveryCase))
        assert job is not None and job.status == "COMPLETED"
        assert action is not None and action.status == "SUCCEEDED"
        assert action.provider_reference == "provider-1"
        assert action.cost_minor_units == 25
        assert case is not None and case.status == RecoveryCaseStatus.ACTION_EXECUTED


def test_worker_last_mile_preflight_cancels_payment_race_without_execution() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        jobs, job_id = setup_job(session, "merchant_race")
        executor = FakeExecutor()
        checker = FakePreflight(
            [PreflightResult(True, "PREFLIGHT_PASSED"), PreflightResult(False, "PAYMENT_VERIFIED")]
        )
        worker = WorkerService(session, "merchant_race", jobs, executor, checker)
        result = worker.process_once(now=datetime(2026, 1, 1, 12, tzinfo=UTC))
        assert result.status == "cancelled"
        assert result.reason_code == "PAYMENT_VERIFIED"
        assert executor.calls == []
        session.rollback()
        assert session.get(ScheduledJob, job_id).status == "CANCELLED"
        assert session.scalar(select(RecoveryAction)).status == "CANCELLED"


def test_worker_provider_failure_retries_and_duplicate_run_is_noop() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        jobs, job_id = setup_job(session, "merchant_retry")
        executor = FakeExecutor(
            ActionExecutionError("provider_timeout", "provider did not respond", retryable=True)
        )
        worker = WorkerService(session, "merchant_retry", jobs, executor)
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        first = worker.process_once(now=now)
        assert first.status == "retry_scheduled"
        session.rollback()
        retry_at = session.get(ScheduledJob, job_id).next_retry_at
        assert retry_at is not None
        session.rollback()
        second = worker.process_once(now=retry_at.replace(tzinfo=UTC))
        assert second.status == "succeeded"
        assert executor.calls == ["worker-action-1", "worker-action-1"]
        session.rollback()
        assert worker.process_once(now=retry_at.replace(tzinfo=UTC)).status == "idle"


def test_worker_terminal_provider_failure_does_not_retry() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        jobs, job_id = setup_job(session, "merchant_terminal")
        executor = FakeExecutor(
            ActionExecutionError(
                "invalid_recipient", "provider rejected the destination", retryable=False
            )
        )
        worker = WorkerService(session, "merchant_terminal", jobs, executor)
        result = worker.process_once(now=datetime(2026, 1, 1, 12, tzinfo=UTC))
        assert result.status == "failed"
        session.rollback()
        job = session.get(ScheduledJob, job_id)
        action = session.scalar(select(RecoveryAction))
        assert job is not None and job.status == "FAILED"
        assert action is not None and action.status == "FAILED"


def test_worker_unexpected_executor_error_becomes_safe_retry_state() -> None:
    class BrokenExecutor:
        def execute(self, work: WorkItem) -> ActionExecutionResult:
            del work
            raise RuntimeError("private provider response")

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        jobs, job_id = setup_job(session, "merchant_unexpected")
        worker = WorkerService(session, "merchant_unexpected", jobs, BrokenExecutor())
        result = worker.process_once(now=datetime(2026, 1, 1, 12, tzinfo=UTC))
        assert result.status == "retry_scheduled"
        assert result.reason_code == "worker_unexpected_error"
        session.rollback()
        job = session.get(ScheduledJob, job_id)
        assert job is not None and job.last_error_safe == "worker execution failed unexpectedly"


def test_worker_restart_recovers_expired_lease_and_run_stops_cleanly() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        jobs, job_id = setup_job(session, "merchant_restart")
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        assert jobs.claim_due(now=now) is not None
        session.rollback()
        restarted = WorkerService(session, "merchant_restart", jobs, FakeExecutor())
        assert restarted.startup_reconcile(now=datetime(2026, 1, 1, 12, 0, 31, tzinfo=UTC)) == 1
        session.rollback()
        assert session.get(ScheduledJob, job_id).status == "PENDING"
        session.rollback()
        stop_event = Event()
        stop_event.set()
        restarted.run(stop_event, clock=lambda: now, poll_interval_seconds=0.01)


def test_worker_restart_requeues_reserved_action_after_expired_lease() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        jobs, job_id = setup_job(session, "merchant_reserved_restart")
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        assert jobs.claim_due(now=now) is not None
        session.rollback()
        job = session.get(ScheduledJob, job_id)
        assert job is not None
        job.status = "CLAIMED"
        job.lease_until = datetime(2026, 1, 1, 12, 0, 30)
        action = session.scalar(select(RecoveryAction))
        assert action is not None
        action.status = "EXECUTING"
        session.commit()

        assert jobs.recover_expired_leases(now=datetime(2026, 1, 1, 12, 0, 31, tzinfo=UTC)) == 1
        session.rollback()
        assert session.get(ScheduledJob, job_id).status == "PENDING"
        action = session.scalar(select(RecoveryAction))
        assert action is not None
        assert action.status == "SCHEDULED"
        assert action.failure_category == "worker_lease_expired"


def test_provider_preflight_cancels_before_effect_when_payment_has_succeeded() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        jobs, job_id = setup_job(session, "merchant_payment_race")
        case = session.scalar(select(RecoveryCase))
        assert case is not None
        session.add(
            PaymentAttempt(
                merchant_id="merchant_payment_race",
                recovery_case_id=case.id,
                external_payment_id="pay-race",
                payment_method="upi",
                provider="simulator",
                amount=10_000,
                currency="INR",
                status="failed",
            )
        )
        session.commit()
        payment = SimulatedPaymentProvider()
        payment.set_status(
            "merchant_payment_race",
            "pay-race",
            PaymentStatus.SUCCEEDED,
            amount_minor_units=10_000,
            currency="INR",
        )
        executor = FakeExecutor()
        worker = WorkerService(
            session,
            "merchant_payment_race",
            jobs,
            executor,
            ProviderPreflightChecker(session, "merchant_payment_race", payment),
        )

        result = worker.process_once(now=datetime(2026, 1, 1, 12, tzinfo=UTC))

        assert result.status == "cancelled"
        assert result.reason_code == "PAYMENT_VERIFIED"
        assert executor.calls == []
        session.rollback()
        assert session.get(ScheduledJob, job_id).status == "CANCELLED"


def test_provider_preflight_retries_when_payment_verification_is_unavailable() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        jobs, job_id = setup_job(session, "merchant_payment_unavailable")
        case = session.scalar(select(RecoveryCase))
        assert case is not None
        session.add(
            PaymentAttempt(
                merchant_id="merchant_payment_unavailable",
                recovery_case_id=case.id,
                external_payment_id="pay-unavailable",
                payment_method="upi",
                provider="simulator",
                amount=10_000,
                currency="INR",
                status="failed",
            )
        )
        session.commit()
        payment = SimulatedPaymentProvider()
        payment.available = False
        worker = WorkerService(
            session,
            "merchant_payment_unavailable",
            jobs,
            FakeExecutor(),
            ProviderPreflightChecker(session, "merchant_payment_unavailable", payment),
        )

        result = worker.process_once(now=datetime(2026, 1, 1, 12, tzinfo=UTC))

        assert result.status == "retry_scheduled"
        assert result.reason_code == "PAYMENT_VERIFICATION_UNAVAILABLE"
        session.rollback()
        job = session.get(ScheduledJob, job_id)
        action = session.scalar(select(RecoveryAction))
        assert job is not None and job.status == "PENDING"
        assert action is not None and action.status == "SCHEDULED"


def test_payment_success_during_provider_execution_preserves_one_auditable_outcome() -> None:
    class PaymentRaceExecutor:
        def __init__(self, session: Session, payment: SimulatedPaymentProvider) -> None:
            self.session = session
            self.payment = payment
            self.calls = 0

        def execute(self, work: WorkItem) -> ActionExecutionResult:
            self.calls += 1
            success = RevenueEvent(
                event_id="evt-worker-provider-race",
                event_type=RevenueEventType.PAYMENT_SUCCEEDED,
                merchant_id="merchant_provider_race",
                source_object_id="order-merchant_provider_race",
                external_obligation_id="order-merchant_provider_race",
                obligation_type="payment",
                payment_id="pay-provider-race",
                amount_minor_units=10_000,
                currency="INR",
                occurred_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
            )
            EventIngestionService(self.session, "simulator").ingest(success)
            self.payment.set_status(
                "merchant_provider_race",
                "pay-provider-race",
                PaymentStatus.SUCCEEDED,
                amount_minor_units=10_000,
                currency="INR",
            )
            PaymentReconciliationService(
                self.session,
                "merchant_provider_race",
                self.payment,
                provider_name="simulator",
            ).reconcile(success)
            return ActionExecutionResult(provider_reference="message-in-flight", cost_minor_units=0)

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        jobs, job_id = setup_job(session, "merchant_provider_race")
        case = session.scalar(select(RecoveryCase))
        assert case is not None
        session.add(
            PaymentAttempt(
                merchant_id="merchant_provider_race",
                recovery_case_id=case.id,
                external_payment_id="pay-provider-race",
                payment_method="upi",
                provider="simulator",
                amount=10_000,
                currency="INR",
                status="failed",
            )
        )
        session.commit()
        payment = SimulatedPaymentProvider()
        payment.set_status("merchant_provider_race", "pay-provider-race", PaymentStatus.FAILED)
        executor = PaymentRaceExecutor(session, payment)
        worker = WorkerService(
            session,
            "merchant_provider_race",
            jobs,
            executor,
            ProviderPreflightChecker(session, "merchant_provider_race", payment),
        )

        result = worker.process_once(now=datetime(2026, 1, 1, 12, tzinfo=UTC))

        assert result.status == "succeeded"
        assert executor.calls == 1
        session.rollback()
        case = session.scalar(select(RecoveryCase))
        job = session.get(ScheduledJob, job_id)
        action = session.scalar(select(RecoveryAction))
        assert case is not None and case.status == RecoveryCaseStatus.RECOVERED
        assert case.recovered_amount == 10_000
        assert job is not None and job.status == "COMPLETED"
        assert action is not None and action.status == "SUCCEEDED"
