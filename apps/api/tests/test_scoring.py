from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.cases.service import RecoveryCaseService
from app.events.contracts import RevenueEvent
from app.events.service import EventIngestionService
from app.persistence.base import Base
from app.persistence.models import RecoveryCase
from app.scoring.diagnosis import RootCause, classify
from app.scoring.economics import ScoringConfig, calculate_score
from app.scoring.service import CaseAnalysisService


def config() -> ScoringConfig:
    return ScoringConfig(50, 10, 20, 50, "scoring-v1")


def test_diagnosis_is_deterministic_and_unknown_is_explicit() -> None:
    assert classify("payment.failed", "UPI_TIMEOUT").category == RootCause.TEMPORARY_PAYMENT_FAILURE
    assert classify("payment.failed", "not_known").category == RootCause.UNKNOWN
    assert classify("payment.failed", None).confidence_percent < 50
    assert classify("checkout.abandoned", None).category == RootCause.CHECKOUT_ABANDONMENT


def test_economics_uses_integer_minor_units() -> None:
    result = calculate_score(
        249900, RootCause.TEMPORARY_PAYMENT_FAILURE, 85, incident_active=False, config=config()
    )
    assert result.probability_percent == 60
    assert result.expected_recoverable_amount == 149940
    assert isinstance(result.expected_recoverable_amount, int)
    with pytest.raises(ValueError):
        calculate_score(-1, RootCause.UNKNOWN, 0, incident_active=False, config=config())


def test_case_analysis_persists_score_and_transitions_case() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        event = RevenueEvent(
            event_id="evt_score",
            event_type="payment.failed",
            merchant_id="merchant_score",
            source_object_id="order_score",
            amount_minor_units=10000,
            currency="INR",
            payment_method="upi",
            failure_code="UPI_TIMEOUT",
            occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        EventIngestionService(session, "simulator").ingest(event)
        case = RecoveryCaseService(session, "simulator", 3).associate(event)
        assert case is not None
        case_id = case.id
        session.rollback()
        result = CaseAnalysisService(session, "merchant_score", config()).analyze(case_id)
        session.rollback()
        assert result.expected_recoverable_amount == 6000
        stored = session.get(RecoveryCase, case_id)
        assert stored is not None
        assert stored.status == "ACTION_PENDING"
        assert stored.recovery_probability == 60
        assert stored.expected_recoverable_amount == 6000
