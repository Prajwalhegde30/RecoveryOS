from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.attribution.metrics import RecoveryMetricsService
from app.attribution.service import (
    AttributionConfig,
    AttributionOutcome,
    AttributionService,
)
from app.persistence.base import Base
from app.persistence.models import (
    AttributionRecord,
    Merchant,
    Obligation,
    PaymentAttempt,
    RecoveryAction,
    RecoveryCase,
    RecoveryCaseStatus,
)

MERCHANT_ID = "merchant-attribution"
OPENED_AT = datetime(2026, 1, 1, 11, 0)


def make_session() -> Session:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(
        Merchant(
            id=MERCHANT_ID,
            external_key="attribution-merchant",
            name="Attribution Merchant",
            default_currency="INR",
            timezone="UTC",
            environment_mode="test",
            status="active",
        )
    )
    session.commit()
    return session


def add_case(
    session: Session,
    *,
    case_id: str,
    status: RecoveryCaseStatus,
    amount: int = 10_000,
    attribution_status: str = "pending",
) -> RecoveryCase:
    obligation = Obligation(
        id=f"obligation-{case_id}",
        merchant_id=MERCHANT_ID,
        obligation_type="payment",
        external_obligation_id=f"order-{case_id}",
        amount_at_risk=amount,
        currency="INR",
        status="closed" if status == RecoveryCaseStatus.RECOVERED else "open",
        authoritative_status="paid" if status == RecoveryCaseStatus.RECOVERED else "unpaid",
    )
    case = RecoveryCase(
        id=case_id,
        merchant_id=MERCHANT_ID,
        obligation_id=obligation.id,
        source_type="payment_failure",
        status=status,
        opened_at=OPENED_AT,
        closed_at=OPENED_AT + timedelta(minutes=20)
        if status == RecoveryCaseStatus.RECOVERED
        else None,
        max_attempts_snapshot=3,
        recovered_amount=amount if status == RecoveryCaseStatus.RECOVERED else 0,
        currency="INR",
        attribution_status=attribution_status,
    )
    session.add_all([obligation, case])
    session.commit()
    return case


def add_success(session: Session, case_id: str, *, at: datetime) -> None:
    session.add(
        PaymentAttempt(
            merchant_id=MERCHANT_ID,
            recovery_case_id=case_id,
            external_payment_id=f"payment-{case_id}",
            payment_method="upi",
            provider="simulator",
            amount=10_000,
            currency="INR",
            status="succeeded",
            provider_event_at=at,
        )
    )
    session.commit()


def test_natural_and_assisted_recovery_are_mutually_exclusive() -> None:
    session = make_session()
    add_case(session, case_id="case-natural", status=RecoveryCaseStatus.RECOVERED)
    add_success(session, "case-natural", at=OPENED_AT + timedelta(minutes=20))
    service = AttributionService(session, MERCHANT_ID, AttributionConfig(timedelta(hours=1)))
    natural = service.attribute_case("case-natural", now=datetime(2026, 1, 1, 12, tzinfo=UTC))
    assert natural.outcome == AttributionOutcome.NATURAL_RECOVERY
    assert natural.recovered_amount_minor_units == 10_000

    add_case(session, case_id="case-assisted", status=RecoveryCaseStatus.RECOVERED)
    add_success(session, "case-assisted", at=OPENED_AT + timedelta(minutes=20))
    session.add(
        RecoveryAction(
            id="action-assisted",
            merchant_id=MERCHANT_ID,
            recovery_case_id="case-assisted",
            action_type="SEND_WHATSAPP",
            status="SUCCEEDED",
            idempotency_key="assisted-action",
            executed_at=OPENED_AT + timedelta(minutes=10),
            cost_minor_units=100,
            correlation_id="test",
        )
    )
    session.commit()
    assisted = service.attribute_case("case-assisted", now=datetime(2026, 1, 1, 12, tzinfo=UTC))
    assert assisted.outcome == AttributionOutcome.ASSISTED_RECOVERY
    assert assisted.qualifying_action_id == "action-assisted"
    assert (
        session.scalar(
            select(AttributionRecord.recovery_case_id).where(
                AttributionRecord.recovery_case_id == "case-natural"
            )
        )
        == "case-natural"
    )
    session.close()


def test_unrecovered_and_suppressed_cases_are_attributed_after_window() -> None:
    session = make_session()
    add_case(session, case_id="case-unrecovered", status=RecoveryCaseStatus.WAITING)
    add_case(
        session,
        case_id="case-suppressed",
        status=RecoveryCaseStatus.SUPPRESSED,
    )
    service = AttributionService(session, MERCHANT_ID, AttributionConfig(timedelta(hours=1)))
    now = datetime(2026, 1, 1, 13, tzinfo=UTC)
    unrecovered = service.attribute_case("case-unrecovered", now=now)
    suppressed = service.attribute_case("case-suppressed", now=now)
    assert unrecovered.outcome == AttributionOutcome.UNRECOVERED
    assert suppressed.outcome == AttributionOutcome.SUPPRESSED
    assert unrecovered.recovered_amount_minor_units == 0
    assert suppressed.recovered_amount_minor_units == 0
    session.close()


def test_attribution_is_idempotent_and_metrics_use_persisted_facts() -> None:
    session = make_session()
    add_case(session, case_id="case-metrics", status=RecoveryCaseStatus.RECOVERED)
    add_success(session, "case-metrics", at=OPENED_AT + timedelta(minutes=20))
    session.add(
        RecoveryAction(
            id="action-metrics",
            merchant_id=MERCHANT_ID,
            recovery_case_id="case-metrics",
            action_type="SEND_SMS",
            status="SUCCEEDED",
            idempotency_key="metrics-action",
            executed_at=OPENED_AT + timedelta(minutes=10),
            cost_minor_units=250,
            correlation_id="test",
        )
    )
    session.commit()
    service = AttributionService(session, MERCHANT_ID, AttributionConfig(timedelta(hours=1)))
    first = service.attribute_case("case-metrics", now=datetime(2026, 1, 1, 12, tzinfo=UTC))
    second = service.attribute_case("case-metrics", now=datetime(2026, 1, 1, 12, tzinfo=UTC))
    assert first.outcome == second.outcome == AttributionOutcome.ASSISTED_RECOVERY
    assert (
        session.scalar(
            select(AttributionRecord).where(AttributionRecord.recovery_case_id == "case-metrics")
        )
        is not None
    )
    metrics = RecoveryMetricsService(session, MERCHANT_ID).calculate()
    assert metrics.revenue_at_risk_minor_units == 10_000
    assert metrics.recovered_minor_units == 10_000
    assert metrics.assisted_recovered_minor_units == 10_000
    assert metrics.recovery_cost_minor_units == 250
    assert metrics.net_recovery_minor_units == 9_750
    assert metrics.recovery_rate_percent == 100
    session.close()
