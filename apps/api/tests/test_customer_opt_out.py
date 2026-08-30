from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.cases.service import RecoveryCaseService
from app.customers.service import CustomerOptOutService
from app.events.contracts import RevenueEvent, RevenueEventType
from app.events.service import EventIngestionService
from app.jobs.service import JobConfig, JobService
from app.persistence.base import Base
from app.persistence.models import (
    AuditEvent,
    Customer,
    Merchant,
    Obligation,
    PolicyDecision,
    PolicyVersion,
    RecoveryAction,
    RecoveryCase,
    RecoveryCaseStatus,
    ScheduledJob,
)
from app.persistence.models import (
    RevenueEvent as RevenueEventRecord,
)

MERCHANT_ID = "merchant-opt-out"
CUSTOMER_ID = "customer-opt-out"


def opt_out_event(event_id: str = "evt-opt-out") -> RevenueEvent:
    return RevenueEvent(
        event_id=event_id,
        event_type=RevenueEventType.CUSTOMER_OPTED_OUT,
        merchant_id=MERCHANT_ID,
        source_object_id=f"preference-{event_id}",
        customer_external_id=CUSTOMER_ID,
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def failed_event() -> RevenueEvent:
    return RevenueEvent(
        event_id="evt-failed-after-opt-out",
        event_type=RevenueEventType.PAYMENT_FAILED,
        merchant_id=MERCHANT_ID,
        source_object_id="order-after-opt-out",
        external_obligation_id="order-after-opt-out",
        obligation_type="payment",
        customer_external_id=CUSTOMER_ID,
        payment_id="pay-after-opt-out",
        amount_minor_units=10_000,
        currency="INR",
        payment_method="upi",
        failure_code="UPI_TIMEOUT",
        occurred_at=datetime(2026, 1, 2, tzinfo=UTC),
    )


def add_merchant(session: Session) -> None:
    session.add(
        Merchant(
            id=MERCHANT_ID,
            external_key=MERCHANT_ID,
            name="Opt-out Merchant",
            default_currency="INR",
            timezone="UTC",
            environment_mode="test",
            status="active",
        )
    )
    session.commit()


def setup_scheduled_case(session: Session) -> tuple[str, str]:
    customer = Customer(
        merchant_id=MERCHANT_ID,
        external_customer_id=CUSTOMER_ID,
        status="active",
    )
    obligation = Obligation(
        merchant_id=MERCHANT_ID,
        obligation_type="payment",
        external_obligation_id="order-opt-out",
        amount_at_risk=10_000,
        currency="INR",
        status="open",
        authoritative_status="unpaid",
    )
    session.add_all((customer, obligation))
    session.flush()
    case = RecoveryCase(
        merchant_id=MERCHANT_ID,
        customer_id=customer.id,
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
        merchant_id=MERCHANT_ID,
        version=1,
        policy_json={},
        created_by="test-admin",
        status="ACTIVE",
    )
    session.add(version)
    session.flush()
    decision = PolicyDecision(
        merchant_id=MERCHANT_ID,
        recovery_case_id=case.id,
        policy_version_id=version.id,
        result="ALLOW",
        decisive_rule="NORMAL_POLICY",
        reason="test action allowed",
        input_snapshot_json={},
        actor_type="system",
        correlation_id="opt-out-test",
    )
    session.add(decision)
    session.flush()
    case_id = case.id
    decision_id = decision.id
    version_id = version.id
    session.commit()
    job = JobService(
        session,
        MERCHANT_ID,
        JobConfig(
            max_attempts=2,
            lease_seconds=30,
            backoff_base_seconds=10,
            backoff_max_seconds=60,
        ),
    ).schedule_action(
        case_id=case_id,
        policy_decision_id=decision_id,
        policy_version_id=version_id,
        action_type="SEND_EMAIL",
        idempotency_key="opt-out-action",
        due_at=datetime(2026, 1, 1, tzinfo=UTC),
        channel="email",
    )
    job_id = job.id
    session.rollback()
    return case_id, job_id


def test_opt_out_cancels_future_work_and_closes_open_cases() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        add_merchant(session)
        case_id, job_id = setup_scheduled_case(session)
        event = opt_out_event()
        EventIngestionService(session, "simulator").ingest(event)

        result = CustomerOptOutService(session, MERCHANT_ID, "simulator").apply(event)

        assert result.duplicate is False
        assert result.affected_case_count == 1
        assert result.cancelled_job_count == 1
        session.rollback()
        customer = session.scalar(select(Customer))
        case = session.get(RecoveryCase, case_id)
        job = session.get(ScheduledJob, job_id)
        action = session.scalar(select(RecoveryAction))
        record = session.scalar(select(RevenueEventRecord))
        assert customer is not None and customer.opted_out_at is not None
        assert case is not None and case.status == RecoveryCaseStatus.OPTED_OUT
        assert job is not None and job.status == "CANCELLED"
        assert action is not None and action.status == "CANCELLED"
        assert record is not None and record.processing_status == "PROCESSED"
        assert session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "CUSTOMER_OPT_OUT_APPLIED")
        )

        duplicate = CustomerOptOutService(session, MERCHANT_ID, "simulator").apply(event)

        assert duplicate.duplicate is True


def test_case_created_after_opt_out_is_terminal_and_never_actionable() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        add_merchant(session)
        preference = opt_out_event()
        EventIngestionService(session, "simulator").ingest(preference)
        CustomerOptOutService(session, MERCHANT_ID, "simulator").apply(preference)
        session.rollback()

        failure = failed_event()
        EventIngestionService(session, "simulator").ingest(failure)
        case = RecoveryCaseService(session, "simulator", 3).associate(failure)

        assert case is not None
        assert case.status == RecoveryCaseStatus.OPTED_OUT
