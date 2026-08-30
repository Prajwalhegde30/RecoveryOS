from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cases.state_machine import TERMINAL_STATES, ActorType, validate_transition
from app.events.contracts import RevenueEvent, RevenueEventType
from app.integrations.contracts import PaymentProvider, PaymentStatus
from app.integrations.errors import ProviderError
from app.persistence.models import (
    AuditEvent,
    JobStatus,
    Obligation,
    PaymentAttempt,
    RecoveryAction,
    RecoveryCase,
    RecoveryCaseStatus,
    ScheduledJob,
)
from app.persistence.models import (
    RevenueEvent as RevenueEventRecord,
)


class ReconciliationOutcome(StrEnum):
    RECOVERED = "RECOVERED"
    DUPLICATE = "DUPLICATE"
    NOT_CONFIRMED = "NOT_CONFIRMED"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"
    UNMATCHED = "UNMATCHED"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    ADJUSTED = "ADJUSTED"
    ADJUSTMENT_IGNORED = "ADJUSTMENT_IGNORED"


@dataclass(frozen=True)
class ReconciliationResult:
    outcome: ReconciliationOutcome
    case_id: str | None
    obligation_id: str | None
    payment_id: str | None
    amount_minor_units: int
    adjustment_amount_minor_units: int
    net_recovered_amount_minor_units: int
    cancelled_job_count: int
    retryable: bool
    reason: str


class PaymentReconciliationService:
    """Makes financial state changes only after provider-confirmed payment status."""

    _SUCCESS_EVENTS = frozenset({RevenueEventType.PAYMENT_SUCCEEDED, RevenueEventType.INVOICE_PAID})
    _ADJUSTMENT_EVENTS = frozenset(
        {RevenueEventType.PAYMENT_REFUNDED, RevenueEventType.PAYMENT_REVERSED}
    )

    def __init__(
        self,
        session: Session,
        merchant_id: str,
        provider: PaymentProvider,
        *,
        provider_name: str,
    ) -> None:
        if not merchant_id or not provider_name:
            raise ValueError("merchant_id and provider_name are required")
        self.session = session
        self.merchant_id = merchant_id
        self.provider = provider
        self.provider_name = provider_name

    def reconcile(self, event: RevenueEvent) -> ReconciliationResult:
        if event.merchant_id != self.merchant_id:
            raise LookupError("reconciliation event is outside merchant scope")
        record = self._event_record(event.event_id)
        if record is None:
            self.session.rollback()
            raise LookupError("reconciliation event must be persisted before reconciliation")
        if record.processing_status == "PROCESSED":
            result = self._result(
                ReconciliationOutcome.DUPLICATE,
                case_id=record.recovery_case_id,
                obligation_id=record.obligation_id,
                payment_id=event.payment_id,
                amount=event.amount_minor_units or 0,
                reason="reconciliation event was already processed",
            )
            self.session.rollback()
            return result
        self.session.rollback()
        if event.event_type in self._SUCCESS_EVENTS:
            return self._reconcile_success(event)
        if event.event_type in self._ADJUSTMENT_EVENTS:
            return self._reconcile_adjustment(event)
        raise ValueError("event type is not a reconciliation event")

    def _reconcile_success(self, event: RevenueEvent) -> ReconciliationResult:
        payment_id = event.payment_id
        if payment_id is None:
            return self._result(
                ReconciliationOutcome.UNMATCHED,
                payment_id=None,
                reason="success event has no payment identity",
            )
        try:
            snapshot = self.provider.get_payment_status(self.merchant_id, payment_id)
        except ProviderError as exc:
            return self._result(
                ReconciliationOutcome.VERIFICATION_UNAVAILABLE,
                payment_id=payment_id,
                retryable=exc.retryable,
                reason=exc.safe_message,
            )
        if snapshot.status != PaymentStatus.SUCCEEDED:
            return self._result(
                ReconciliationOutcome.NOT_CONFIRMED,
                payment_id=payment_id,
                reason="provider has not confirmed payment success",
            )
        if snapshot.amount_minor_units is None or snapshot.currency is None:
            return self._result(
                ReconciliationOutcome.INVALID_AMOUNT,
                payment_id=payment_id,
                reason="provider success is missing amount or currency",
            )
        return self._apply_success(
            event, payment_id, snapshot.amount_minor_units, snapshot.currency
        )

    def _apply_success(
        self, event: RevenueEvent, payment_id: str, amount: int, currency: str
    ) -> ReconciliationResult:
        with self.session.begin():
            obligation = self._find_obligation(event, for_update=True)
            if obligation is None:
                return self._result(
                    ReconciliationOutcome.UNMATCHED,
                    payment_id=payment_id,
                    reason="success does not match a known obligation",
                )
            case = self._case_for_obligation(obligation.id, for_update=True)
            if case is None:
                return self._result(
                    ReconciliationOutcome.UNMATCHED,
                    obligation_id=obligation.id,
                    payment_id=payment_id,
                    reason="successful obligation has no recovery case",
                )
            if (
                amount != obligation.amount_at_risk
                or currency.upper() != obligation.currency.upper()
            ):
                return self._result(
                    ReconciliationOutcome.INVALID_AMOUNT,
                    case_id=case.id,
                    obligation_id=obligation.id,
                    payment_id=payment_id,
                    amount=amount,
                    reason="provider amount or currency does not match obligation",
                )
            attempt = self._payment_attempt(payment_id, for_update=True)
            if obligation.authoritative_status in {"paid", "succeeded"} or (
                attempt is not None and attempt.status == "succeeded"
            ):
                self._associate_event(event, obligation.id, case.id)
                return self._result(
                    ReconciliationOutcome.DUPLICATE,
                    case_id=case.id,
                    obligation_id=obligation.id,
                    payment_id=payment_id,
                    amount=amount,
                    net_amount=case.recovered_amount,
                    reason="payment success was already reconciled",
                )
            if attempt is None:
                attempt = PaymentAttempt(
                    merchant_id=self.merchant_id,
                    recovery_case_id=case.id,
                    external_payment_id=payment_id,
                    payment_method="provider_confirmed",
                    provider=self.provider_name,
                    amount=amount,
                    currency=currency.upper(),
                    status="succeeded",
                    provider_event_at=_utc_naive(event.occurred_at),
                )
                self.session.add(attempt)
            else:
                attempt.status = "succeeded"
                attempt.amount = amount
                attempt.currency = currency.upper()
                attempt.provider_event_at = _utc_naive(event.occurred_at)
            obligation.status = "closed"
            obligation.authoritative_status = "paid"
            obligation.paid_at = _utc_naive(event.occurred_at)
            case.recovered_amount = amount
            if case.status != RecoveryCaseStatus.RECOVERED:
                current = RecoveryCaseStatus(case.status)
                if current in TERMINAL_STATES:
                    self.session.add(
                        AuditEvent(
                            merchant_id=self.merchant_id,
                            entity_type="recovery_case",
                            entity_id=case.id,
                            event_type="TERMINAL_CASE_PAYMENT_RECONCILED",
                            actor_type=ActorType.SYSTEM,
                            from_state=current,
                            to_state=current,
                            reason="payment reconciled without reopening terminal case",
                            metadata_safe_json={
                                "payment_id": payment_id,
                                "amount_minor_units": amount,
                                "currency": currency.upper(),
                            },
                            correlation_id=event.correlation_id or "payment-reconciliation",
                        )
                    )
                else:
                    validate_transition(current, RecoveryCaseStatus.RECOVERED)
                    case.status = RecoveryCaseStatus.RECOVERED
                    case.closed_at = _utc_naive(event.occurred_at)
                    self.session.add(
                        AuditEvent(
                            merchant_id=self.merchant_id,
                            entity_type="recovery_case",
                            entity_id=case.id,
                            event_type="CASE_RECOVERED",
                            actor_type=ActorType.SYSTEM,
                            from_state=current,
                            to_state=RecoveryCaseStatus.RECOVERED,
                            reason="provider-confirmed payment success reconciled",
                            metadata_safe_json={
                                "payment_id": payment_id,
                                "amount_minor_units": amount,
                                "currency": currency.upper(),
                            },
                            correlation_id=event.correlation_id or "payment-reconciliation",
                        )
                    )
            self._associate_event(event, obligation.id, case.id)
            cancelled = self._cancel_future_work(case.id, event.correlation_id)
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="obligation",
                    entity_id=obligation.id,
                    event_type="PAYMENT_RECONCILED",
                    actor_type=ActorType.SYSTEM,
                    reason="provider-confirmed payment is authoritative",
                    metadata_safe_json={
                        "case_id": case.id,
                        "payment_id": payment_id,
                        "amount_minor_units": amount,
                        "currency": currency.upper(),
                        "cancelled_job_count": cancelled,
                    },
                    correlation_id=event.correlation_id or "payment-reconciliation",
                )
            )
            return self._result(
                ReconciliationOutcome.RECOVERED,
                case_id=case.id,
                obligation_id=obligation.id,
                payment_id=payment_id,
                amount=amount,
                cancelled_jobs=cancelled,
                reason="provider-confirmed payment recovered obligation",
            )

    def _reconcile_adjustment(self, event: RevenueEvent) -> ReconciliationResult:
        payment_id = event.payment_id
        if payment_id is None:
            return self._result(
                ReconciliationOutcome.UNMATCHED,
                reason="adjustment event has no payment identity",
            )
        try:
            snapshot = self.provider.get_payment_status(self.merchant_id, payment_id)
        except ProviderError as exc:
            return self._result(
                ReconciliationOutcome.VERIFICATION_UNAVAILABLE,
                payment_id=payment_id,
                retryable=exc.retryable,
                reason=exc.safe_message,
            )
        expected_status = (
            PaymentStatus.REFUNDED
            if event.event_type == RevenueEventType.PAYMENT_REFUNDED
            else PaymentStatus.REVERSED
        )
        if snapshot.status != expected_status:
            return self._result(
                ReconciliationOutcome.NOT_CONFIRMED,
                payment_id=payment_id,
                reason="provider has not confirmed the requested adjustment",
            )
        if (
            snapshot.currency is not None
            and snapshot.currency.upper() != (event.currency or "").upper()
        ):
            return self._result(
                ReconciliationOutcome.INVALID_AMOUNT,
                payment_id=payment_id,
                reason="provider adjustment currency does not match event currency",
            )
        with self.session.begin():
            obligation = self._find_obligation(event, for_update=True)
            if obligation is None:
                return self._result(
                    ReconciliationOutcome.UNMATCHED,
                    payment_id=payment_id,
                    reason="adjustment does not match a known obligation",
                )
            case = self._case_for_obligation(obligation.id, for_update=True)
            if case is None:
                return self._result(
                    ReconciliationOutcome.UNMATCHED,
                    obligation_id=obligation.id,
                    payment_id=payment_id,
                    reason="adjustment obligation has no recovery case",
                )
            amount = (
                event.amount_minor_units
                if event.amount_minor_units is not None
                else obligation.amount_at_risk
            )
            if amount < 0 or amount > obligation.amount_at_risk:
                return self._result(
                    ReconciliationOutcome.INVALID_AMOUNT,
                    case_id=case.id,
                    obligation_id=obligation.id,
                    payment_id=payment_id,
                    amount=amount,
                    reason="adjustment exceeds obligation amount",
                )
            previous_adjustment = self._previous_adjustment_amount(case.id, payment_id)
            gross_amount = case.recovered_amount + previous_adjustment
            remaining = gross_amount - previous_adjustment
            if remaining <= 0:
                self._associate_event(event, obligation.id, case.id)
                return self._result(
                    ReconciliationOutcome.ADJUSTMENT_IGNORED,
                    case_id=case.id,
                    obligation_id=obligation.id,
                    payment_id=payment_id,
                    amount=amount,
                    reason="no unreversed recovered amount remains",
                )
            if amount > remaining:
                return self._result(
                    ReconciliationOutcome.INVALID_AMOUNT,
                    case_id=case.id,
                    obligation_id=obligation.id,
                    payment_id=payment_id,
                    amount=amount,
                    reason="cumulative adjustment exceeds recovered amount",
                )
            case.recovered_amount = remaining - amount
            obligation.authoritative_status = expected_status.value
            attempt = self._payment_attempt(payment_id, for_update=True)
            if attempt is not None:
                attempt.status = expected_status.value
            self._associate_event(event, obligation.id, case.id)
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="obligation",
                    entity_id=obligation.id,
                    event_type="PAYMENT_ADJUSTED",
                    actor_type=ActorType.SYSTEM,
                    reason="provider-confirmed refund or reversal applied as adjustment",
                    metadata_safe_json={
                        "case_id": case.id,
                        "payment_id": payment_id,
                        "adjustment_amount_minor_units": amount,
                        "net_recovered_amount_minor_units": case.recovered_amount,
                        "adjustment_type": expected_status.value,
                    },
                    correlation_id=event.correlation_id or "payment-reconciliation",
                )
            )
            return self._result(
                ReconciliationOutcome.ADJUSTED,
                case_id=case.id,
                obligation_id=obligation.id,
                payment_id=payment_id,
                amount=amount,
                adjustment=amount,
                net_amount=case.recovered_amount,
                reason="provider-confirmed adjustment applied without deleting success history",
            )

    def _find_obligation(self, event: RevenueEvent, *, for_update: bool) -> Obligation | None:
        obligation_type = event.obligation_type or _default_obligation_type(event.event_type)
        external_id = event.external_obligation_id or event.source_object_id
        statement = select(Obligation).where(
            Obligation.merchant_id == self.merchant_id,
            Obligation.obligation_type == obligation_type,
            Obligation.external_obligation_id == external_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def _case_for_obligation(self, obligation_id: str, *, for_update: bool) -> RecoveryCase | None:
        statement = select(RecoveryCase).where(
            RecoveryCase.merchant_id == self.merchant_id,
            RecoveryCase.obligation_id == obligation_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def _payment_attempt(self, payment_id: str, *, for_update: bool) -> PaymentAttempt | None:
        statement = select(PaymentAttempt).where(
            PaymentAttempt.merchant_id == self.merchant_id,
            PaymentAttempt.external_payment_id == payment_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def _associate_event(self, event: RevenueEvent, obligation_id: str, case_id: str) -> None:
        record = self.session.scalar(
            select(RevenueEventRecord).where(
                RevenueEventRecord.merchant_id == self.merchant_id,
                RevenueEventRecord.provider == self.provider_name,
                RevenueEventRecord.external_event_id == event.event_id,
            )
        )
        if record is not None:
            record.obligation_id = obligation_id
            record.recovery_case_id = case_id
            record.processing_status = "PROCESSED"
            record.processed_at = _utc_naive(datetime.now(UTC))

    def _event_record(self, event_id: str) -> RevenueEventRecord | None:
        return self.session.scalar(
            select(RevenueEventRecord).where(
                RevenueEventRecord.merchant_id == self.merchant_id,
                RevenueEventRecord.provider == self.provider_name,
                RevenueEventRecord.external_event_id == event_id,
            )
        )

    def _previous_adjustment_amount(self, case_id: str, payment_id: str) -> int:
        records = self.session.scalars(
            select(RevenueEventRecord).where(
                RevenueEventRecord.merchant_id == self.merchant_id,
                RevenueEventRecord.recovery_case_id == case_id,
                RevenueEventRecord.event_type.in_(
                    [
                        RevenueEventType.PAYMENT_REFUNDED,
                        RevenueEventType.PAYMENT_REVERSED,
                    ]
                ),
            )
        ).all()
        total = 0
        for record in records:
            payload = record.normalized_payload
            if payload.get("payment_id") == payment_id:
                value = payload.get("amount_minor_units")
                if isinstance(value, int) and value >= 0:
                    total += value
        return total

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
                if action is not None and action.status == "SCHEDULED":
                    action.status = "CANCELLED"
                    action.cancelled_at = _utc_naive(datetime.now(UTC))
                elif action is not None and action.status == "EXECUTING":
                    # An external effect may already be in flight. Leave the
                    # claimed job and action intact so the worker can persist
                    # its result after the payment reconciliation commits.
                    self.session.add(
                        AuditEvent(
                            merchant_id=self.merchant_id,
                            entity_type="scheduled_job",
                            entity_id=job.id,
                            event_type="ACTIVE_ACTION_LEFT_TO_FINISH",
                            actor_type=ActorType.SYSTEM,
                            reason="active external effect was not cancelled after payment success",
                            metadata_safe_json={"case_id": case_id, "action_id": action.id},
                            correlation_id=correlation_id or "payment-reconciliation",
                        )
                    )
                    continue
            job.status = JobStatus.CANCELLED
            job.lease_until = None
            cancelled += 1
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="scheduled_job",
                    entity_id=job.id,
                    event_type="STALE_ACTION_CANCELLED",
                    actor_type=ActorType.SYSTEM,
                    reason="future recovery work cancelled after payment success",
                    metadata_safe_json={"case_id": case_id},
                    correlation_id=correlation_id or "payment-reconciliation",
                )
            )
        return cancelled

    def _result(
        self,
        outcome: ReconciliationOutcome,
        *,
        case_id: str | None = None,
        obligation_id: str | None = None,
        payment_id: str | None = None,
        amount: int = 0,
        adjustment: int = 0,
        net_amount: int = 0,
        cancelled_jobs: int = 0,
        retryable: bool = False,
        reason: str,
    ) -> ReconciliationResult:
        return ReconciliationResult(
            outcome=outcome,
            case_id=case_id,
            obligation_id=obligation_id,
            payment_id=payment_id,
            amount_minor_units=amount,
            adjustment_amount_minor_units=adjustment,
            net_recovered_amount_minor_units=net_amount,
            cancelled_job_count=cancelled_jobs,
            retryable=retryable,
            reason=reason,
        )


def _default_obligation_type(event_type: RevenueEventType) -> str:
    if event_type in {
        RevenueEventType.INVOICE_PAID,
    }:
        return "invoice"
    return "payment"


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(UTC).replace(tzinfo=None)
