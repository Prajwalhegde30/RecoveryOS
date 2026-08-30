from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.cases.service import RecoveryCaseService
from app.events.contracts import RevenueEvent, RevenueEventType
from app.events.service import EventIngestionService
from app.persistence.base import Base
from app.persistence.models import Obligation, PaymentAttempt, RecoveryCase


def make_event(event_id: str, external_id: str = "order_1") -> RevenueEvent:
    return RevenueEvent(
        event_id=event_id,
        event_type="payment.failed",
        merchant_id="merchant_1",
        source_object_id=external_id,
        external_obligation_id=external_id,
        customer_external_id="customer_1",
        payment_id=f"pay_{event_id}",
        amount_minor_units=249900,
        currency="INR",
        payment_method="upi",
        failure_code="UPI_TIMEOUT",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def session_for_cases() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_one_case_associates_multiple_events_and_attempts() -> None:
    with session_for_cases() as session:
        first = make_event("evt_case_1")
        EventIngestionService(session, "simulator").ingest(first)
        service = RecoveryCaseService(session, "simulator", 3)
        case = service.associate(first)
        assert case is not None
        assert case.status == "DETECTED"
        session.rollback()

        second = make_event("evt_case_2")
        EventIngestionService(session, "simulator").ingest(second)
        same_case = service.associate(second)

        assert same_case is not None
        assert same_case.id == case.id
        assert session.scalar(select(func.count()).select_from(Obligation)) == 1
        assert session.scalar(select(func.count()).select_from(RecoveryCase)) == 1
        assert session.scalar(select(func.count()).select_from(PaymentAttempt)) == 2


def test_non_recoverable_success_event_does_not_open_case() -> None:
    with session_for_cases() as session:
        success = make_event("evt_success").model_copy(
            update={"event_type": RevenueEventType.PAYMENT_SUCCEEDED}
        )
        EventIngestionService(session, "simulator").ingest(success)
        assert RecoveryCaseService(session, "simulator", 3).associate(success) is None
        assert session.scalar(select(func.count()).select_from(RecoveryCase)) == 0


def test_recoverable_event_without_money_is_rejected() -> None:
    with session_for_cases() as session:
        incomplete_data = make_event("evt_incomplete").model_dump()
        incomplete_data["amount_minor_units"] = None
        incomplete_data["currency"] = None
        incomplete = RevenueEvent(**incomplete_data)
        EventIngestionService(session, "simulator").ingest(incomplete)
        with pytest.raises(ValueError, match="amount_minor_units"):
            RecoveryCaseService(session, "simulator", 3).associate(incomplete)
