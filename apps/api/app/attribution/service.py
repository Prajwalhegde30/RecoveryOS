from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cases.state_machine import ActorType
from app.persistence.models import (
    AttributionRecord,
    AuditEvent,
    PaymentAttempt,
    RecoveryAction,
    RecoveryCase,
    RecoveryCaseStatus,
)


class AttributionOutcome(StrEnum):
    NATURAL_RECOVERY = "NATURAL_RECOVERY"
    ASSISTED_RECOVERY = "ASSISTED_RECOVERY"
    SUPPRESSED = "SUPPRESSED"
    UNRECOVERED = "UNRECOVERED"


@dataclass(frozen=True)
class AttributionConfig:
    window: timedelta
    version: str = "attribution-v1"

    def __post_init__(self) -> None:
        if self.window <= timedelta(0):
            raise ValueError("attribution window must be positive")
        if not self.version:
            raise ValueError("attribution version is required")


@dataclass(frozen=True)
class AttributionResult:
    case_id: str
    outcome: AttributionOutcome | None
    recovered_amount_minor_units: int
    adjustment_amount_minor_units: int
    qualifying_action_id: str | None
    pending: bool
    reason: str


class AttributionService:
    """Creates one case-level attribution record from persisted financial facts."""

    def __init__(self, session: Session, merchant_id: str, config: AttributionConfig) -> None:
        if not merchant_id:
            raise ValueError("merchant_id is required")
        self.session = session
        self.merchant_id = merchant_id
        self.config = config

    def attribute_case(
        self,
        case_id: str,
        *,
        now: datetime,
        correlation_id: str = "attribution",
    ) -> AttributionResult:
        now_naive = _utc_naive(now)
        transaction = (
            self.session.begin_nested() if self.session.in_transaction() else self.session.begin()
        )
        with transaction:
            case = self.session.scalar(
                select(RecoveryCase)
                .where(
                    RecoveryCase.id == case_id,
                    RecoveryCase.merchant_id == self.merchant_id,
                )
                .with_for_update()
            )
            if case is None:
                raise LookupError("recovery case not found")
            existing = self.session.scalar(
                select(AttributionRecord).where(
                    AttributionRecord.recovery_case_id == case_id,
                    AttributionRecord.merchant_id == self.merchant_id,
                )
            )
            if existing is not None:
                self._refresh_amounts(existing, case)
                return AttributionResult(
                    case_id=case.id,
                    outcome=AttributionOutcome(existing.outcome),
                    recovered_amount_minor_units=existing.recovered_amount,
                    adjustment_amount_minor_units=existing.adjustment_amount,
                    qualifying_action_id=existing.qualifying_action_id,
                    pending=False,
                    reason="case attribution already exists and was refreshed",
                )

            start = _case_opened_at(case)
            end = start + self.config.window
            success = self._success_attempt(case.id)
            if success is None and now_naive < end:
                return AttributionResult(
                    case_id=case.id,
                    outcome=None,
                    recovered_amount_minor_units=0,
                    adjustment_amount_minor_units=0,
                    qualifying_action_id=None,
                    pending=True,
                    reason="case window is still open and no verified success exists",
                )
            success_time = success.provider_event_at if success is not None else None
            qualifying = self._qualifying_action(case.id, start, end, success_time)
            if success is not None and success_time is not None:
                outcome = (
                    AttributionOutcome.ASSISTED_RECOVERY
                    if qualifying is not None and success_time <= end
                    else AttributionOutcome.NATURAL_RECOVERY
                )
                amount = case.recovered_amount
                reason = "verified success classified from case and action chronology"
                payment_id = success.external_payment_id
            elif case.status == RecoveryCaseStatus.SUPPRESSED:
                outcome = AttributionOutcome.SUPPRESSED
                amount = 0
                reason = "case window ended while intervention was suppressed"
                payment_id = None
            else:
                outcome = AttributionOutcome.UNRECOVERED
                amount = 0
                reason = "case window ended without a verified success"
                payment_id = None
            adjustment = self._adjustment_amount(case.id)
            record = AttributionRecord(
                merchant_id=self.merchant_id,
                recovery_case_id=case.id,
                outcome=outcome,
                qualifying_action_id=qualifying.id if qualifying is not None else None,
                attribution_window_start=start,
                attribution_window_end=end,
                verified_payment_id=payment_id,
                recovered_amount=amount,
                adjustment_amount=adjustment,
                confidence=100 if success is not None else None,
                limitations="case-level measured attribution; not causal proof",
            )
            self.session.add(record)
            case.attribution_status = outcome.value
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="recovery_case",
                    entity_id=case.id,
                    event_type="CASE_ATTRIBUTED",
                    actor_type=ActorType.SYSTEM,
                    reason=reason,
                    metadata_safe_json={
                        "outcome": outcome.value,
                        "recovered_amount_minor_units": amount,
                        "adjustment_amount_minor_units": adjustment,
                        "qualifying_action_id": qualifying.id if qualifying else None,
                        "attribution_version": self.config.version,
                    },
                    correlation_id=correlation_id,
                )
            )
            return AttributionResult(
                case_id=case.id,
                outcome=outcome,
                recovered_amount_minor_units=amount,
                adjustment_amount_minor_units=adjustment,
                qualifying_action_id=qualifying.id if qualifying is not None else None,
                pending=False,
                reason=reason,
            )

    def _success_attempt(self, case_id: str) -> PaymentAttempt | None:
        return self.session.scalar(
            select(PaymentAttempt)
            .where(
                PaymentAttempt.merchant_id == self.merchant_id,
                PaymentAttempt.recovery_case_id == case_id,
                PaymentAttempt.status == "succeeded",
                PaymentAttempt.provider_event_at.is_not(None),
            )
            .order_by(PaymentAttempt.provider_event_at.asc(), PaymentAttempt.created_at.asc())
        )

    def _qualifying_action(
        self,
        case_id: str,
        start: datetime,
        end: datetime,
        success_time: datetime | None,
    ) -> RecoveryAction | None:
        statement = (
            select(RecoveryAction)
            .where(
                RecoveryAction.merchant_id == self.merchant_id,
                RecoveryAction.recovery_case_id == case_id,
                RecoveryAction.status == "SUCCEEDED",
                RecoveryAction.executed_at.is_not(None),
                RecoveryAction.executed_at >= start,
                RecoveryAction.executed_at <= end,
            )
            .order_by(RecoveryAction.executed_at.asc(), RecoveryAction.id.asc())
        )
        if success_time is not None:
            statement = statement.where(RecoveryAction.executed_at <= success_time)
        return self.session.scalar(statement)

    def _adjustment_amount(self, case_id: str) -> int:
        records = self.session.scalars(
            select(AuditEvent).where(
                AuditEvent.merchant_id == self.merchant_id,
                AuditEvent.entity_type == "obligation",
                AuditEvent.event_type == "PAYMENT_ADJUSTED",
                AuditEvent.metadata_safe_json["case_id"].as_string() == case_id,
            )
        )
        return sum(
            int(event.metadata_safe_json.get("adjustment_amount_minor_units", 0))
            for event in records
        )

    def _refresh_amounts(self, record: AttributionRecord, case: RecoveryCase) -> None:
        record.recovered_amount = case.recovered_amount
        record.adjustment_amount = self._adjustment_amount(case.id)


def _case_opened_at(case: RecoveryCase) -> datetime:
    if case.opened_at.tzinfo is not None:
        return case.opened_at.astimezone(UTC).replace(tzinfo=None)
    return case.opened_at


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(UTC).replace(tzinfo=None)
