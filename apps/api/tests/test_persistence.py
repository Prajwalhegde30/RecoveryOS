import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.persistence.base import Base
from app.persistence.models import Merchant, Obligation, RecoveryCase


def test_schema_contains_financial_identity_constraints() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    assert "recovery_cases" in inspector.get_table_names()
    assert "scheduled_jobs" in inspector.get_table_names()
    assert any(
        {"merchant_id", "obligation_type", "external_obligation_id"}.issubset(
            set(item["column_names"])
        )
        for item in inspector.get_unique_constraints("obligations")
    )
    assert any(
        {"merchant_id", "provider", "external_event_id"}.issubset(set(item["column_names"]))
        for item in inspector.get_unique_constraints("revenue_events")
    )


def test_one_recovery_case_per_obligation_is_enforced() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    with sessions.begin() as session:
        merchant = Merchant(
            external_key="merchant_1",
            name="Demo Merchant",
            default_currency="INR",
            timezone="Asia/Kolkata",
            environment_mode="demo",
            status="active",
        )
        session.add(merchant)
        session.flush()
        obligation = Obligation(
            merchant_id=merchant.id,
            obligation_type="payment",
            external_obligation_id="order_1",
            amount_at_risk=249900,
            currency="INR",
            status="open",
            authoritative_status="failed",
        )
        session.add(obligation)
        session.flush()
        session.add_all(
            [
                RecoveryCase(
                    merchant_id=merchant.id,
                    obligation_id=obligation.id,
                    source_type="payment_failure",
                    status="open",
                    max_attempts_snapshot=3,
                    currency="INR",
                    attribution_status="pending",
                ),
                RecoveryCase(
                    merchant_id=merchant.id,
                    obligation_id=obligation.id,
                    source_type="duplicate_webhook",
                    status="open",
                    max_attempts_snapshot=3,
                    currency="INR",
                    attribution_status="pending",
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            with session.begin_nested():
                session.flush()
