from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cases.state_machine import TERMINAL_STATES, ActorType, validate_transition
from app.events.contracts import RevenueEvent, RevenueEventType
from app.persistence.models import (
    AuditEvent,
    Customer,
    JobStatus,
    RecoveryAction,
    RecoveryCase,
    RecoveryCaseStatus,
    ScheduledJob,
)
from app.persistence.models import RevenueEvent as RevenueEventRecord


@dataclass(frozen=True)
class CustomerOptOutResult:
    customer_id: str | None
    affected_case_count: int
    cancelled_job_count: int
    duplicate: bool


class CustomerOptOutService:
    """Persists an opt-out and stops future customer-facing recovery work."""

    def __init__(self, session: Session, merchant_id: str, provider_name: str) -> None:
        if not merchant_id or not provider_name:
            raise ValueError("merchant_id and provider_name are required")
        self.session = session
        self.merchant_id = merchant_id
        self.provider_name = provider_name

    def apply(self, event: RevenueEvent) -> CustomerOptOutResult:
        if event.merchant_id != self.merchant_id:
            raise LookupError("opt-out event is outside merchant scope")
        if event.event_type != RevenueEventType.CUSTOMER_OPTED_OUT:
            raise ValueError("event is not a customer opt-out")
        if event.customer_external_id is None:
            raise ValueError("customer opt-out requires customer_external_id")
        record = self._event_record(event.event_id)
        if record is None:
            self.session.rollback()
            raise LookupError("opt-out event must be persisted before application")
        if record.processing_status == "PROCESSED":
            self.session.rollback()
            return CustomerOptOutResult(
                customer_id=None,
                affected_case_count=0,
                cancelled_job_count=0,
                duplicate=True,
            )
        self.session.rollback()
        with self.session.begin():
            record = self._event_record(event.event_id, for_update=True)
            if record is None:
                raise LookupError("opt-out event must be persisted before application")
            if record.processing_status == "PROCESSED":
                return CustomerOptOutResult(None, 0, 0, True)
            customer = self.session.scalar(
                select(Customer)
                .where(
                    Customer.merchant_id == self.merchant_id,
                    Customer.external_customer_id == event.customer_external_id,
                )
                .with_for_update()
            )
            occurred_at = _utc_naive(event.occurred_at)
            if customer is None:
                customer = Customer(
                    merchant_id=self.merchant_id,
                    external_customer_id=event.customer_external_id,
                    status="opted_out",
                    opted_out_at=occurred_at,
                )
                self.session.add(customer)
                self.session.flush()
            else:
                customer.status = "opted_out"
                customer.opted_out_at = occurred_at
            cases = list(
                self.session.scalars(
                    select(RecoveryCase)
                    .where(
                        RecoveryCase.merchant_id == self.merchant_id,
                        RecoveryCase.customer_id == customer.id,
                    )
                    .with_for_update()
                ).all()
            )
            affected_cases = 0
            cancelled_jobs = 0
            for case in cases:
                if RecoveryCaseStatus(case.status) not in TERMINAL_STATES:
                    current = RecoveryCaseStatus(case.status)
                    validate_transition(current, RecoveryCaseStatus.OPTED_OUT)
                    case.status = RecoveryCaseStatus.OPTED_OUT
                    case.closed_at = occurred_at
                    affected_cases += 1
                    self.session.add(
                        AuditEvent(
                            merchant_id=self.merchant_id,
                            entity_type="recovery_case",
                            entity_id=case.id,
                            event_type="CASE_OPTED_OUT",
                            actor_type=ActorType.SYSTEM,
                            from_state=current,
                            to_state=RecoveryCaseStatus.OPTED_OUT,
                            reason="customer opt-out prevents future recovery outreach",
                            metadata_safe_json={"event_id": event.event_id},
                            correlation_id=event.correlation_id or "customer-opt-out",
                        )
                    )
                cancelled_jobs += self._cancel_future_work(case.id, event.correlation_id)
            record.processing_status = "PROCESSED"
            record.processed_at = _utc_naive(datetime.now(UTC))
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="customer",
                    entity_id=customer.id,
                    event_type="CUSTOMER_OPT_OUT_APPLIED",
                    actor_type=ActorType.SYSTEM,
                    reason="customer contact preference updated from normalized event",
                    metadata_safe_json={
                        "event_id": event.event_id,
                        "affected_case_count": affected_cases,
                        "cancelled_job_count": cancelled_jobs,
                    },
                    correlation_id=event.correlation_id or "customer-opt-out",
                )
            )
            return CustomerOptOutResult(
                customer_id=customer.id,
                affected_case_count=affected_cases,
                cancelled_job_count=cancelled_jobs,
                duplicate=False,
            )

    def _event_record(
        self, event_id: str, *, for_update: bool = False
    ) -> RevenueEventRecord | None:
        statement = select(RevenueEventRecord).where(
            RevenueEventRecord.merchant_id == self.merchant_id,
            RevenueEventRecord.provider == self.provider_name,
            RevenueEventRecord.external_event_id == event_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def _cancel_future_work(self, case_id: str, correlation_id: str | None) -> int:
        jobs = list(
            self.session.scalars(
                select(ScheduledJob)
                .where(
                    ScheduledJob.merchant_id == self.merchant_id,
                    ScheduledJob.recovery_case_id == case_id,
                    ScheduledJob.status.in_([JobStatus.PENDING, JobStatus.CLAIMED]),
                )
                .with_for_update()
            ).all()
        )
        cancelled = 0
        for job in jobs:
            action = None
            if job.recovery_action_id is not None:
                action = self.session.scalar(
                    select(RecoveryAction)
                    .where(
                        RecoveryAction.id == job.recovery_action_id,
                        RecoveryAction.merchant_id == self.merchant_id,
                        RecoveryAction.status.in_(["SCHEDULED", "EXECUTING"]),
                    )
                    .with_for_update()
                )
            if action is not None and action.status == "EXECUTING":
                self.session.add(
                    AuditEvent(
                        merchant_id=self.merchant_id,
                        entity_type="scheduled_job",
                        entity_id=job.id,
                        event_type="ACTIVE_ACTION_LEFT_TO_FINISH",
                        actor_type=ActorType.SYSTEM,
                        reason="active external effect was not cancelled after customer opt-out",
                        metadata_safe_json={"case_id": case_id, "action_id": action.id},
                        correlation_id=correlation_id or "customer-opt-out",
                    )
                )
                continue
            job.status = JobStatus.CANCELLED
            job.lease_until = None
            cancelled += 1
            if action is not None:
                action.status = "CANCELLED"
                action.cancelled_at = _utc_naive(datetime.now(UTC))
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="scheduled_job",
                    entity_id=job.id,
                    event_type="STALE_ACTION_CANCELLED",
                    actor_type=ActorType.SYSTEM,
                    reason="future recovery work cancelled after customer opt-out",
                    metadata_safe_json={"case_id": case_id},
                    correlation_id=correlation_id or "customer-opt-out",
                )
            )
        return cancelled


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(UTC).replace(tzinfo=None)
