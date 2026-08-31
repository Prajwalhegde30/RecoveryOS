from datetime import UTC

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cases.identity import obligation_identity
from app.events.contracts import RevenueEvent
from app.persistence.models import (
    AuditEvent,
    Customer,
    Obligation,
    PaymentAttempt,
    RecoveryCase,
)
from app.persistence.models import (
    RevenueEvent as RevenueEventRecord,
)


class RecoveryCaseService:
    def __init__(self, session: Session, provider: str, max_attempts: int) -> None:
        self.session = session
        self.provider = provider
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        self.max_attempts = max_attempts

    def associate(self, event: RevenueEvent) -> RecoveryCase | None:
        identity = obligation_identity(event)
        if identity is None:
            return None
        if event.amount_minor_units is None or event.currency is None:
            raise ValueError("recoverable event requires amount_minor_units and currency")

        try:
            with self.session.begin():
                obligation = self.session.scalar(
                    select(Obligation).where(
                        Obligation.merchant_id == event.merchant_id,
                        Obligation.obligation_type == identity.obligation_type,
                        Obligation.external_obligation_id == identity.external_id,
                    )
                )
                if obligation is None:
                    obligation = Obligation(
                        merchant_id=event.merchant_id,
                        obligation_type=identity.obligation_type,
                        external_obligation_id=identity.external_id,
                        amount_at_risk=event.amount_minor_units,
                        currency=event.currency,
                        status="open",
                        authoritative_status="unpaid",
                    )
                    self.session.add(obligation)
                    self.session.flush()

                case = self.session.scalar(
                    select(RecoveryCase).where(
                        RecoveryCase.merchant_id == event.merchant_id,
                        RecoveryCase.obligation_id == obligation.id,
                    )
                )
                if case is None:
                    customer = self._customer(event)
                    initial_status = (
                        "OPTED_OUT" if customer and customer.opted_out_at else "DETECTED"
                    )
                    case = RecoveryCase(
                        merchant_id=event.merchant_id,
                        customer_id=customer.id if customer else None,
                        obligation_id=obligation.id,
                        source_type=event.event_type,
                        status=initial_status,
                        attempt_count=0,
                        max_attempts_snapshot=self.max_attempts,
                        recovered_amount=0,
                        currency=event.currency,
                        attribution_status="pending",
                        opened_at=event.occurred_at.astimezone(UTC).replace(tzinfo=None),
                    )
                    self.session.add(case)
                    self.session.flush()
                    self.session.add(
                        AuditEvent(
                            merchant_id=event.merchant_id,
                            entity_type="recovery_case",
                            entity_id=case.id,
                            event_type="CASE_CREATED",
                            actor_type="system",
                            reason="eligible revenue event associated with obligation",
                            metadata_safe_json={
                                "event_id": event.event_id,
                                "provider": self.provider,
                                "customer_opted_out": initial_status == "OPTED_OUT",
                            },
                            correlation_id=event.correlation_id or "generated",
                        )
                    )
                self._associate_event(event, obligation.id, case.id)
                self._associate_attempt(event, case.id)
                return case
        except IntegrityError:
            self.session.rollback()
            obligation = self.session.scalar(
                select(Obligation).where(
                    Obligation.merchant_id == event.merchant_id,
                    Obligation.obligation_type == identity.obligation_type,
                    Obligation.external_obligation_id == identity.external_id,
                )
            )
            if obligation is None:
                raise
            return self.session.scalar(
                select(RecoveryCase).where(
                    RecoveryCase.merchant_id == event.merchant_id,
                    RecoveryCase.obligation_id == obligation.id,
                )
            )

    def _customer(self, event: RevenueEvent) -> Customer | None:
        if event.customer_external_id is None:
            return None
        customer = self.session.scalar(
            select(Customer).where(
                Customer.merchant_id == event.merchant_id,
                Customer.external_customer_id == event.customer_external_id,
            )
        )
        if customer is None:
            customer = Customer(
                merchant_id=event.merchant_id,
                external_customer_id=event.customer_external_id,
                status="active",
            )
            self.session.add(customer)
            self.session.flush()
        return customer

    def _associate_event(self, event: RevenueEvent, obligation_id: str, case_id: str) -> None:
        record = self.session.scalar(
            select(RevenueEventRecord).where(
                RevenueEventRecord.merchant_id == event.merchant_id,
                RevenueEventRecord.provider == self.provider,
                RevenueEventRecord.external_event_id == event.event_id,
            )
        )
        if record is not None:
            record.obligation_id = obligation_id
            record.recovery_case_id = case_id
            record.processing_status = "PROCESSED"

    def _associate_attempt(self, event: RevenueEvent, case_id: str) -> None:
        if event.payment_id is None:
            return
        attempt = self.session.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.merchant_id == event.merchant_id,
                PaymentAttempt.provider == self.provider,
                PaymentAttempt.external_payment_id == event.payment_id,
            )
        )
        if attempt is None:
            self.session.add(
                PaymentAttempt(
                    merchant_id=event.merchant_id,
                    recovery_case_id=case_id,
                    external_payment_id=event.payment_id,
                    payment_method=event.payment_method or "unknown",
                    provider=self.provider,
                    amount=event.amount_minor_units or 0,
                    currency=event.currency or "XXX",
                    status="failed",
                    failure_code=event.failure_code,
                    provider_event_at=event.occurred_at.replace(tzinfo=None),
                )
            )
