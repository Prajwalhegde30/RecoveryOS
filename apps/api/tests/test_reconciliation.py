from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.cases.service import RecoveryCaseService
from app.events.contracts import RevenueEvent, RevenueEventType
from app.events.service import EventIngestionService
from app.integrations.contracts import PaymentStatus
from app.integrations.simulated import SimulatedPaymentProvider
from app.jobs.service import JobConfig, JobService
from app.persistence.base import Base
from app.persistence.models import (
    AuditEvent,
    Merchant,
    Obligation,
    PaymentAttempt,
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
from app.reconciliation.service import PaymentReconciliationService, ReconciliationOutcome


def session_for_reconciliation() -> Session:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine)


def failed_event(
    event_id: str = "evt-failed", *, merchant_id: str = "merchant-reconcile"
) -> RevenueEvent:
    return RevenueEvent(
        event_id=event_id,
        event_type=RevenueEventType.PAYMENT_FAILED,
        merchant_id=merchant_id,
        source_object_id="order-reconcile",
        external_obligation_id="order-reconcile",
        obligation_type="payment",
        customer_external_id="customer-reconcile",
        payment_id="pay-reconcile",
        amount_minor_units=10_000,
        currency="INR",
        payment_method="upi",
        failure_code="UPI_TIMEOUT",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def success_event(failed: RevenueEvent, event_id: str = "evt-success") -> RevenueEvent:
    return failed.model_copy(
        update={
            "event_id": event_id,
            "event_type": RevenueEventType.PAYMENT_SUCCEEDED,
            "failure_code": None,
        }
    )


def setup_case(session: Session) -> tuple[RevenueEvent, str]:
    session.add(
        Merchant(
            id="merchant-reconcile",
            external_key="reconcile-merchant",
            name="Reconciliation Merchant",
            default_currency="INR",
            timezone="UTC",
            environment_mode="test",
            status="active",
        )
    )
    session.commit()
    event = failed_event()
    EventIngestionService(session, "simulator").ingest(event)
    case = RecoveryCaseService(session, "simulator", 3).associate(event)
    assert case is not None
    case_id = case.id
    session.rollback()
    return event, case_id


def setup_scheduled_case(session: Session) -> tuple[RevenueEvent, str, str]:
    event, case_id = setup_case(session)
    with session.begin():
        case = session.get(RecoveryCase, case_id)
        assert case is not None
        case.status = RecoveryCaseStatus.POLICY_CHECK
        version = PolicyVersion(
            merchant_id=event.merchant_id,
            version=1,
            policy_json={},
            created_by="test-admin",
            status="ACTIVE",
        )
        session.add(version)
        session.flush()
        decision = PolicyDecision(
            merchant_id=event.merchant_id,
            recovery_case_id=case_id,
            policy_version_id=version.id,
            result="ALLOW",
            decisive_rule="NORMAL_POLICY",
            reason="test action allowed",
            input_snapshot_json={},
            actor_type="system",
            correlation_id="reconcile-test",
        )
        session.add(decision)
        session.flush()
        decision_id = decision.id
        version_id = version.id
    job = JobService(
        session,
        event.merchant_id,
        JobConfig(
            max_attempts=2, lease_seconds=30, backoff_base_seconds=10, backoff_max_seconds=60
        ),
    ).schedule_action(
        case_id=case_id,
        policy_decision_id=decision_id,
        policy_version_id=version_id,
        action_type="SEND_EMAIL",
        idempotency_key="reconcile-action",
        due_at=datetime(2026, 1, 1, tzinfo=UTC),
        channel="email",
    )
    job_id = job.id
    session.rollback()
    return event, case_id, job_id


def persist_event(session: Session, event: RevenueEvent) -> None:
    EventIngestionService(session, "simulator").ingest(event)


def test_success_reconciliation_is_authoritative_and_cancels_future_work() -> None:
    with session_for_reconciliation() as session:
        failed, case_id, job_id = setup_scheduled_case(session)
        success = success_event(failed)
        persist_event(session, success)
        provider = SimulatedPaymentProvider()
        provider.set_status(
            failed.merchant_id,
            failed.payment_id or "",
            PaymentStatus.SUCCEEDED,
            amount_minor_units=10_000,
            currency="INR",
        )

        result = PaymentReconciliationService(
            session, failed.merchant_id, provider, provider_name="simulator"
        ).reconcile(success)

        assert result.outcome == ReconciliationOutcome.RECOVERED
        assert result.amount_minor_units == 10_000
        session.rollback()
        case = session.get(RecoveryCase, case_id)
        obligation = session.scalar(select(Obligation))
        attempt = session.scalar(select(PaymentAttempt))
        job = session.get(ScheduledJob, job_id)
        action = session.scalar(select(RecoveryAction))
        assert case is not None and case.status == RecoveryCaseStatus.RECOVERED
        assert case.recovered_amount == 10_000
        assert obligation is not None and obligation.authoritative_status == "paid"
        assert attempt is not None and attempt.status == "succeeded"
        assert job is not None and job.status == "CANCELLED"
        assert action is not None and action.status == "CANCELLED"
        assert session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "PAYMENT_RECONCILED")
        )


def test_unconfirmed_or_mismatched_success_cannot_mutate_financial_state() -> None:
    with session_for_reconciliation() as session:
        failed, case_id = setup_case(session)
        success = success_event(failed)
        persist_event(session, success)
        provider = SimulatedPaymentProvider()
        service = PaymentReconciliationService(
            session, failed.merchant_id, provider, provider_name="simulator"
        )
        provider.set_status(failed.merchant_id, failed.payment_id or "", PaymentStatus.PENDING)
        assert service.reconcile(success).outcome == ReconciliationOutcome.NOT_CONFIRMED
        session.rollback()
        assert session.get(RecoveryCase, case_id).status == RecoveryCaseStatus.DETECTED
        session.rollback()

        mismatched = success_event(failed, "evt-success-mismatch")
        persist_event(session, mismatched)
        provider.set_status(
            failed.merchant_id,
            failed.payment_id or "",
            PaymentStatus.SUCCEEDED,
            amount_minor_units=9_999,
            currency="INR",
        )
        assert service.reconcile(mismatched).outcome == ReconciliationOutcome.INVALID_AMOUNT
        session.rollback()
        assert session.get(RecoveryCase, case_id).recovered_amount == 0


def test_unavailable_payment_verification_keeps_event_retryable_without_financial_mutation() -> (
    None
):
    with session_for_reconciliation() as session:
        failed, case_id = setup_case(session)
        success = success_event(failed)
        persist_event(session, success)
        provider = SimulatedPaymentProvider()
        provider.available = False

        result = PaymentReconciliationService(
            session, failed.merchant_id, provider, provider_name="simulator"
        ).reconcile(success)

        assert result.outcome == ReconciliationOutcome.VERIFICATION_UNAVAILABLE
        assert result.retryable is True
        session.rollback()
        case = session.get(RecoveryCase, case_id)
        record = session.scalar(
            select(RevenueEventRecord).where(
                RevenueEventRecord.external_event_id == success.event_id
            )
        )
        assert case is not None and case.recovered_amount == 0
        assert record is not None and record.processing_status == "RECEIVED"


def test_duplicate_success_is_a_noop_even_if_provider_is_unavailable_after_first_success() -> None:
    with session_for_reconciliation() as session:
        failed, case_id = setup_case(session)
        success = success_event(failed)
        persist_event(session, success)
        provider = SimulatedPaymentProvider()
        provider.set_status(
            failed.merchant_id,
            failed.payment_id or "",
            PaymentStatus.SUCCEEDED,
            amount_minor_units=10_000,
            currency="INR",
        )
        service = PaymentReconciliationService(
            session, failed.merchant_id, provider, provider_name="simulator"
        )
        assert service.reconcile(success).outcome == ReconciliationOutcome.RECOVERED
        provider.available = False
        assert service.reconcile(success).outcome == ReconciliationOutcome.DUPLICATE
        session.rollback()
        assert session.get(RecoveryCase, case_id).recovered_amount == 10_000
        assert (
            session.scalar(
                select(RevenueEventRecord).where(
                    RevenueEventRecord.external_event_id == success.event_id
                )
            ).processing_status
            == "PROCESSED"
        )


def test_distinct_duplicate_success_events_cannot_recover_the_same_obligation_twice() -> None:
    with session_for_reconciliation() as session:
        failed, case_id = setup_case(session)
        first_success = success_event(failed, "evt-success-first")
        duplicate_success = success_event(failed, "evt-success-retry")
        persist_event(session, first_success)
        persist_event(session, duplicate_success)
        provider = SimulatedPaymentProvider()
        provider.set_status(
            failed.merchant_id,
            failed.payment_id or "",
            PaymentStatus.SUCCEEDED,
            amount_minor_units=10_000,
            currency="INR",
        )
        service = PaymentReconciliationService(
            session, failed.merchant_id, provider, provider_name="simulator"
        )

        assert service.reconcile(first_success).outcome == ReconciliationOutcome.RECOVERED
        assert service.reconcile(duplicate_success).outcome == ReconciliationOutcome.DUPLICATE

        session.rollback()
        case = session.get(RecoveryCase, case_id)
        attempts = session.scalars(select(PaymentAttempt)).all()
        assert case is not None and case.recovered_amount == 10_000
        assert len(attempts) == 1


def test_success_for_an_unknown_obligation_does_not_mutate_known_financial_state() -> None:
    with session_for_reconciliation() as session:
        failed, case_id = setup_case(session)
        unknown = success_event(failed).model_copy(
            update={
                "event_id": "evt-unknown-obligation",
                "source_object_id": "order-not-known",
                "external_obligation_id": "order-not-known",
            }
        )
        persist_event(session, unknown)
        provider = SimulatedPaymentProvider()
        provider.set_status(
            failed.merchant_id,
            failed.payment_id or "",
            PaymentStatus.SUCCEEDED,
            amount_minor_units=10_000,
            currency="INR",
        )

        result = PaymentReconciliationService(
            session, failed.merchant_id, provider, provider_name="simulator"
        ).reconcile(unknown)

        assert result.outcome == ReconciliationOutcome.UNMATCHED
        session.rollback()
        case = session.get(RecoveryCase, case_id)
        assert case is not None and case.recovered_amount == 0


def test_refund_is_an_explicit_idempotent_adjustment() -> None:
    with session_for_reconciliation() as session:
        failed, case_id = setup_case(session)
        success = success_event(failed)
        persist_event(session, success)
        provider = SimulatedPaymentProvider()
        payment_id = failed.payment_id or ""
        provider.set_status(
            failed.merchant_id,
            payment_id,
            PaymentStatus.SUCCEEDED,
            amount_minor_units=10_000,
            currency="INR",
        )
        service = PaymentReconciliationService(
            session, failed.merchant_id, provider, provider_name="simulator"
        )
        assert service.reconcile(success).outcome == ReconciliationOutcome.RECOVERED
        refund = success_event(failed, "evt-refund").model_copy(
            update={
                "event_type": RevenueEventType.PAYMENT_REFUNDED,
                "amount_minor_units": 4_000,
            }
        )
        persist_event(session, refund)
        provider.set_status(
            failed.merchant_id,
            payment_id,
            PaymentStatus.REFUNDED,
            amount_minor_units=10_000,
            currency="INR",
        )
        adjusted = service.reconcile(refund)
        assert adjusted.outcome == ReconciliationOutcome.ADJUSTED
        assert adjusted.net_recovered_amount_minor_units == 6_000
        provider.available = False
        assert service.reconcile(refund).outcome == ReconciliationOutcome.DUPLICATE
        session.rollback()
        case = session.get(RecoveryCase, case_id)
        attempt = session.scalar(select(PaymentAttempt))
        assert case is not None and case.recovered_amount == 6_000
        assert attempt is not None and attempt.status == "refunded"


def test_reversal_is_a_subsequent_financial_adjustment_without_deleting_success_history() -> None:
    with session_for_reconciliation() as session:
        failed, case_id = setup_case(session)
        success = success_event(failed)
        persist_event(session, success)
        provider = SimulatedPaymentProvider()
        payment_id = failed.payment_id or ""
        provider.set_status(
            failed.merchant_id,
            payment_id,
            PaymentStatus.SUCCEEDED,
            amount_minor_units=10_000,
            currency="INR",
        )
        service = PaymentReconciliationService(
            session, failed.merchant_id, provider, provider_name="simulator"
        )
        assert service.reconcile(success).outcome == ReconciliationOutcome.RECOVERED
        reversal = success_event(failed, "evt-reversal").model_copy(
            update={
                "event_type": RevenueEventType.PAYMENT_REVERSED,
                "amount_minor_units": 10_000,
            }
        )
        persist_event(session, reversal)
        provider.set_status(
            failed.merchant_id,
            payment_id,
            PaymentStatus.REVERSED,
            amount_minor_units=10_000,
            currency="INR",
        )

        adjusted = service.reconcile(reversal)

        assert adjusted.outcome == ReconciliationOutcome.ADJUSTED
        assert adjusted.net_recovered_amount_minor_units == 0
        session.rollback()
        case = session.get(RecoveryCase, case_id)
        assert case is not None and case.recovered_amount == 0


def test_success_with_an_alternate_payment_identity_creates_one_new_attempt_for_the_case() -> None:
    with session_for_reconciliation() as session:
        failed, case_id = setup_case(session)
        alternate = success_event(failed, "evt-success-alternate").model_copy(
            update={"payment_id": "pay-alternate"}
        )
        persist_event(session, alternate)
        provider = SimulatedPaymentProvider()
        provider.set_status(
            failed.merchant_id,
            "pay-alternate",
            PaymentStatus.SUCCEEDED,
            amount_minor_units=10_000,
            currency="INR",
        )
        result = PaymentReconciliationService(
            session, failed.merchant_id, provider, provider_name="simulator"
        ).reconcile(alternate)
        assert result.outcome == ReconciliationOutcome.RECOVERED
        session.rollback()
        assert session.get(RecoveryCase, case_id).status == RecoveryCaseStatus.RECOVERED
        attempts = session.scalars(select(PaymentAttempt)).all()
        assert len(attempts) == 2
        assert {attempt.external_payment_id for attempt in attempts} == {
            "pay-reconcile",
            "pay-alternate",
        }


def test_success_after_terminal_opt_out_reconciles_money_without_reopening_outreach() -> None:
    with session_for_reconciliation() as session:
        failed, case_id = setup_case(session)
        with session.begin():
            case = session.get(RecoveryCase, case_id)
            assert case is not None
            case.status = RecoveryCaseStatus.OPTED_OUT
        success = success_event(failed, "evt-success-after-opt-out")
        persist_event(session, success)
        provider = SimulatedPaymentProvider()
        provider.set_status(
            failed.merchant_id,
            failed.payment_id or "",
            PaymentStatus.SUCCEEDED,
            amount_minor_units=10_000,
            currency="INR",
        )

        result = PaymentReconciliationService(
            session, failed.merchant_id, provider, provider_name="simulator"
        ).reconcile(success)

        assert result.outcome == ReconciliationOutcome.RECOVERED
        session.rollback()
        case = session.get(RecoveryCase, case_id)
        assert case is not None and case.status == RecoveryCaseStatus.OPTED_OUT
        assert case.recovered_amount == 10_000
        assert session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "TERMINAL_CASE_PAYMENT_RECONCILED")
        )


def test_success_does_not_cancel_an_action_already_executing() -> None:
    with session_for_reconciliation() as session:
        failed, case_id, job_id = setup_scheduled_case(session)
        with session.begin():
            job = session.get(ScheduledJob, job_id)
            action = session.scalar(select(RecoveryAction))
            assert job is not None and action is not None
            job.status = "CLAIMED"
            action.status = "EXECUTING"
        success = success_event(failed)
        persist_event(session, success)
        provider = SimulatedPaymentProvider()
        provider.set_status(
            failed.merchant_id,
            failed.payment_id or "",
            PaymentStatus.SUCCEEDED,
            amount_minor_units=10_000,
            currency="INR",
        )

        result = PaymentReconciliationService(
            session, failed.merchant_id, provider, provider_name="simulator"
        ).reconcile(success)

        assert result.outcome == ReconciliationOutcome.RECOVERED
        assert result.cancelled_job_count == 0
        session.rollback()
        job = session.get(ScheduledJob, job_id)
        action = session.scalar(select(RecoveryAction))
        assert job is not None and job.status == "CLAIMED"
        assert action is not None and action.status == "EXECUTING"
        assert session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "ACTIVE_ACTION_LEFT_TO_FINISH")
        )
        session.rollback()
        JobService(
            session,
            failed.merchant_id,
            JobConfig(
                max_attempts=2,
                lease_seconds=30,
                backoff_base_seconds=10,
                backoff_max_seconds=60,
            ),
        ).complete(job_id, provider_reference="message-race", cost_minor_units=0)
        session.rollback()
        job = session.get(ScheduledJob, job_id)
        action = session.scalar(select(RecoveryAction))
        case = session.get(RecoveryCase, case_id)
        assert job is not None and job.status == "COMPLETED"
        assert action is not None and action.status == "SUCCEEDED"
        assert case is not None and case.status == RecoveryCaseStatus.RECOVERED


def test_reconciliation_requires_a_persisted_event_and_rejects_cross_tenant_event() -> None:
    with session_for_reconciliation() as session:
        failed, _ = setup_case(session)
        provider = SimulatedPaymentProvider()
        service = PaymentReconciliationService(
            session, failed.merchant_id, provider, provider_name="simulator"
        )
        success = success_event(failed)
        with pytest.raises(LookupError, match="persisted"):
            service.reconcile(success)
        with pytest.raises(LookupError, match="outside merchant scope"):
            service.reconcile(success.model_copy(update={"merchant_id": "other-merchant"}))
