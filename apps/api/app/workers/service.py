from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cases.state_machine import ActorType, validate_transition
from app.integrations.contracts import PaymentProvider, PaymentStatus
from app.integrations.errors import ProviderError
from app.jobs.service import JobService
from app.persistence.models import (
    AuditEvent,
    Customer,
    JobStatus,
    Obligation,
    PaymentAttempt,
    RecoveryAction,
    RecoveryCase,
    RecoveryCaseStatus,
    ScheduledJob,
)
from app.workers.contracts import (
    ActionExecutionError,
    ActionExecutor,
    PreflightChecker,
    PreflightResult,
    WorkItem,
)
from app.workers.heartbeat import WorkerHeartbeatService


class DefaultPreflightChecker:
    """Conservative checker used until payment/provider adapters are configured."""

    def check(self, work: WorkItem, *, now: datetime) -> PreflightResult:
        del now
        if work.case_status in {
            RecoveryCaseStatus.RECOVERED,
            RecoveryCaseStatus.OPTED_OUT,
            RecoveryCaseStatus.CANCELLED,
            RecoveryCaseStatus.EXHAUSTED,
        }:
            return PreflightResult(False, "TERMINAL_CASE")
        return PreflightResult(True, "PREFLIGHT_PASSED")


class ProviderPreflightChecker:
    """Conservatively verifies case, customer, obligation, and payment state."""

    def __init__(self, session: Session, merchant_id: str, payment: PaymentProvider) -> None:
        self.session = session
        self.merchant_id = merchant_id
        self.payment = payment

    def check(self, work: WorkItem, *, now: datetime) -> PreflightResult:
        del now
        case = self.session.scalar(
            select(RecoveryCase).where(
                RecoveryCase.id == work.case_id,
                RecoveryCase.merchant_id == self.merchant_id,
            )
        )
        if case is None:
            return PreflightResult(
                False, "CASE_NOT_FOUND", safe_message="recovery case is unavailable"
            )
        if case.status in {
            RecoveryCaseStatus.RECOVERED,
            RecoveryCaseStatus.OPTED_OUT,
            RecoveryCaseStatus.CANCELLED,
            RecoveryCaseStatus.EXHAUSTED,
        }:
            return PreflightResult(
                False,
                "TERMINAL_CASE",
                safe_message="recovery case is no longer actionable",
            )
        if case.incident_suppressed or case.status == RecoveryCaseStatus.SUPPRESSED:
            return PreflightResult(
                False,
                "INCIDENT_SUPPRESSED",
                safe_message="recovery action is suppressed during an incident",
            )
        if case.customer_id is not None:
            customer = self.session.scalar(
                select(Customer).where(
                    Customer.id == case.customer_id,
                    Customer.merchant_id == self.merchant_id,
                )
            )
            if customer is None:
                return PreflightResult(
                    False, "CUSTOMER_NOT_FOUND", safe_message="customer contact is unavailable"
                )
            if customer.opted_out_at is not None:
                return PreflightResult(
                    False,
                    "CUSTOMER_OPTED_OUT",
                    safe_message="customer has opted out of recovery outreach",
                )
        obligation = self.session.scalar(
            select(Obligation).where(
                Obligation.id == case.obligation_id,
                Obligation.merchant_id == self.merchant_id,
            )
        )
        if obligation is None:
            return PreflightResult(
                False,
                "OBLIGATION_NOT_FOUND",
                safe_message="recoverable obligation is unavailable",
            )
        if obligation.authoritative_status in {"paid", "succeeded", "refunded", "reversed"}:
            return PreflightResult(
                False, "PAYMENT_VERIFIED", safe_message="payment is no longer outstanding"
            )
        if work.payment_id is None:
            return PreflightResult(True, "PREFLIGHT_PASSED")
        try:
            snapshot = self.payment.get_payment_status(self.merchant_id, work.payment_id)
        except ProviderError:
            return PreflightResult(
                False,
                "PAYMENT_VERIFICATION_UNAVAILABLE",
                retryable=True,
                safe_message="payment verification unavailable; retry scheduled",
            )
        if snapshot.status == PaymentStatus.FAILED:
            return PreflightResult(True, "PREFLIGHT_PASSED")
        if snapshot.status in {
            PaymentStatus.SUCCEEDED,
            PaymentStatus.REFUNDED,
            PaymentStatus.REVERSED,
        }:
            return PreflightResult(
                False, "PAYMENT_VERIFIED", safe_message="payment is no longer outstanding"
            )
        return PreflightResult(
            False,
            "PAYMENT_STATUS_PENDING",
            retryable=True,
            safe_message="payment status is not final; recovery action will be retried",
        )


@dataclass(frozen=True)
class WorkerRunResult:
    status: str
    job_id: str | None = None
    reason_code: str | None = None


class WorkerService:
    """Claims durable jobs and delegates bounded external effects to an executor."""

    def __init__(
        self,
        session: Session,
        merchant_id: str,
        jobs: JobService,
        executor: ActionExecutor,
        preflight: PreflightChecker | None = None,
        worker_id: str = "worker",
    ) -> None:
        self.session = session
        self.merchant_id = merchant_id
        self.jobs = jobs
        self.executor = executor
        self.preflight = preflight or DefaultPreflightChecker()
        self.heartbeat = WorkerHeartbeatService(session, merchant_id, worker_id)

    def startup_reconcile(self, *, now: datetime) -> int:
        return self.jobs.recover_expired_leases(now=now)

    def process_once(self, *, now: datetime) -> WorkerRunResult:
        job = self.jobs.claim_due(now=now)
        if job is None:
            return WorkerRunResult("idle")
        job_id = job.id
        self.session.rollback()
        work = self._load_work(job_id)
        if work is None:
            self.jobs.cancel(job_id, reason="job references missing action or case")
            return WorkerRunResult("cancelled", job_id, "MISSING_WORK")
        first_check = self.preflight.check(work, now=now)
        self.session.rollback()
        if not first_check.allowed:
            return self._handle_preflight_block(job_id, first_check, now)
        if not self._reserve_execution(job_id, work):
            self.jobs.cancel(job_id, reason="job was no longer claimable")
            return WorkerRunResult("cancelled", job_id, "STALE_JOB")
        self.session.rollback()
        last_check = self.preflight.check(work, now=now)
        self.session.rollback()
        if not last_check.allowed:
            return self._handle_preflight_block(job_id, last_check, now)
        try:
            result = self.executor.execute(work)
        except ActionExecutionError as exc:
            if exc.category in {
                "payment_verified",
                "payment_not_outstanding",
                "customer_opted_out",
            }:
                self.jobs.cancel(job_id, reason=exc.safe_message)
                return WorkerRunResult("cancelled", job_id, exc.category)
            job = self.jobs.retry_or_fail(
                job_id,
                now=now,
                error_category=exc.category,
                error_safe=exc.safe_message,
                retryable=exc.retryable,
            )
            return WorkerRunResult(
                "retry_scheduled" if job.status == JobStatus.PENDING else "failed",
                job_id,
                exc.category,
            )
        except Exception:
            job = self.jobs.retry_or_fail(
                job_id,
                now=now,
                error_category="worker_unexpected_error",
                error_safe="worker execution failed unexpectedly",
                retryable=True,
            )
            return WorkerRunResult(
                "retry_scheduled" if job.status == JobStatus.PENDING else "failed",
                job_id,
                "worker_unexpected_error",
            )
        self.session.rollback()
        self.jobs.complete(
            job_id,
            provider_reference=result.provider_reference,
            cost_minor_units=result.cost_minor_units,
        )
        self._mark_case_executed(work.case_id)
        return WorkerRunResult("succeeded", job_id)

    def _handle_preflight_block(
        self, job_id: str, result: PreflightResult, now: datetime
    ) -> WorkerRunResult:
        if result.retryable:
            job = self.jobs.retry_or_fail(
                job_id,
                now=now,
                error_category=result.reason_code,
                error_safe=result.safe_message,
                retryable=True,
            )
            return WorkerRunResult(
                "retry_scheduled" if job.status == JobStatus.PENDING else "failed",
                job_id,
                result.reason_code,
            )
        self.jobs.cancel(job_id, reason=result.safe_message)
        return WorkerRunResult("cancelled", job_id, result.reason_code)

    def run(
        self,
        stop_event: Event,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        poll_interval_seconds: float = 1,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        self.startup_reconcile(now=clock())
        self.heartbeat.beat()
        while not stop_event.is_set():
            self.heartbeat.beat()
            self.process_once(now=clock())
            stop_event.wait(poll_interval_seconds)

    def _load_work(self, job_id: str) -> WorkItem | None:
        with self.session.begin():
            job = self.session.scalar(
                select(ScheduledJob).where(
                    ScheduledJob.id == job_id,
                    ScheduledJob.merchant_id == self.merchant_id,
                )
            )
            if job is None or job.recovery_action_id is None or job.recovery_case_id is None:
                return None
            action = self.session.scalar(
                select(RecoveryAction).where(
                    RecoveryAction.id == job.recovery_action_id,
                    RecoveryAction.merchant_id == self.merchant_id,
                )
            )
            case = self.session.scalar(
                select(RecoveryCase).where(
                    RecoveryCase.id == job.recovery_case_id,
                    RecoveryCase.merchant_id == self.merchant_id,
                )
            )
            if action is None or case is None or action.policy_version_id != job.policy_version_id:
                return None
            if action.status != "SCHEDULED":
                return None
            if job.status != JobStatus.CLAIMED:
                return None
            if job.policy_version_id is None:
                return None
            obligation = self.session.scalar(
                select(Obligation).where(
                    Obligation.id == case.obligation_id,
                    Obligation.merchant_id == self.merchant_id,
                )
            )
            if obligation is None:
                return None
            customer_external_id = None
            if case.customer_id is not None:
                customer = self.session.scalar(
                    select(Customer).where(
                        Customer.id == case.customer_id,
                        Customer.merchant_id == self.merchant_id,
                    )
                )
                customer_external_id = customer.external_customer_id if customer else None
            payment = self.session.scalar(
                select(PaymentAttempt)
                .where(
                    PaymentAttempt.recovery_case_id == case.id,
                    PaymentAttempt.merchant_id == self.merchant_id,
                )
                .order_by(PaymentAttempt.created_at.desc())
            )
            return WorkItem(
                job_id=job.id,
                action_id=action.id,
                case_id=case.id,
                action_type=action.action_type,
                action_idempotency_key=action.idempotency_key,
                policy_version_id=job.policy_version_id,
                case_status=case.status,
                channel=action.channel,
                customer_external_id=customer_external_id,
                obligation_id=obligation.id,
                amount_minor_units=obligation.amount_at_risk,
                currency=obligation.currency,
                payment_id=payment.external_payment_id if payment else None,
            )

    def _reserve_execution(self, job_id: str, work: WorkItem) -> bool:
        with self.session.begin():
            job = self.session.scalar(
                select(ScheduledJob)
                .where(
                    ScheduledJob.id == job_id,
                    ScheduledJob.merchant_id == self.merchant_id,
                    ScheduledJob.status == JobStatus.CLAIMED,
                )
                .with_for_update()
            )
            action = self.session.scalar(
                select(RecoveryAction)
                .where(
                    RecoveryAction.id == work.action_id,
                    RecoveryAction.merchant_id == self.merchant_id,
                    RecoveryAction.status == "SCHEDULED",
                )
                .with_for_update()
            )
            if job is None or action is None or job.policy_version_id != work.policy_version_id:
                return False
            action.status = "EXECUTING"
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="recovery_action",
                    entity_id=action.id,
                    event_type="ACTION_EXECUTION_STARTED",
                    actor_type=ActorType.WORKER,
                    reason="worker reserved action after last-mile checks",
                    metadata_safe_json={
                        "job_id": job.id,
                        "idempotency_key": action.idempotency_key,
                    },
                    correlation_id=job.correlation_id,
                )
            )
            return True

    def _mark_case_executed(self, case_id: str) -> None:
        with self.session.begin():
            case = self.session.scalar(
                select(RecoveryCase)
                .where(
                    RecoveryCase.id == case_id,
                    RecoveryCase.merchant_id == self.merchant_id,
                )
                .with_for_update()
            )
            if case is None or case.status != RecoveryCaseStatus.SCHEDULED:
                return
            validate_transition(RecoveryCaseStatus.SCHEDULED, RecoveryCaseStatus.ACTION_EXECUTED)
            case.status = RecoveryCaseStatus.ACTION_EXECUTED
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="recovery_case",
                    entity_id=case.id,
                    event_type="CASE_STATE_CHANGED",
                    actor_type=ActorType.WORKER,
                    from_state=RecoveryCaseStatus.SCHEDULED,
                    to_state=RecoveryCaseStatus.ACTION_EXECUTED,
                    reason="scheduled action completed",
                    metadata_safe_json={},
                    correlation_id="worker-execution",
                )
            )
