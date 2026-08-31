import hashlib
import hmac
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db_session
from app.config import get_settings
from app.events.contracts import RevenueEvent, RevenueEventType
from app.events.security import verify_signature
from app.events.service import EventIngestionService
from app.main import app
from app.persistence.base import Base
from app.persistence.models import (
    AuditEvent,
    Customer,
    Obligation,
    PaymentAttempt,
    ProcessedEvent,
    Recommendation,
    RecoveryCase,
    RecoveryCaseStatus,
)
from app.persistence.models import RevenueEvent as RevenueEventRecord


def event(event_id: str = "evt_1") -> RevenueEvent:
    return RevenueEvent(
        event_id=event_id,
        event_type="payment.failed",
        merchant_id="merchant_1",
        source_object_id="order_1",
        external_obligation_id="order_1",
        obligation_type="payment",
        payment_method="upi",
        failure_code="UPI_TIMEOUT",
        amount_minor_units=249900,
        currency="inr",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_event_contract_normalizes_currency_and_requires_timezone() -> None:
    normalized = event()
    assert normalized.currency == "INR"
    with pytest.raises(ValueError, match="timezone"):
        invalid = normalized.model_dump()
        invalid["occurred_at"] = datetime(2026, 1, 1)
        RevenueEvent(**invalid)

    with pytest.raises(ValueError, match="provided together"):
        RevenueEvent(
            event_id="evt_bad",
            event_type="payment.failed",
            merchant_id="merchant_1",
            source_object_id="order_1",
            amount_minor_units=100,
            occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_signature_verification_uses_constant_time_digest_comparison() -> None:
    payload = b'{"event_id":"evt_1"}'
    secret = "test-secret"
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_signature(payload, f"sha256={digest}", secret)
    assert not verify_signature(payload, "sha256=bad", secret)
    assert not verify_signature(payload, None, secret)


def test_event_ingestion_is_idempotent_and_persists_normalized_facts() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = EventIngestionService(session, "simulator")
        first = service.ingest(event())
        second = service.ingest(event())

        assert first.duplicate is False
        assert second.duplicate is True
        assert first.correlation_id == second.correlation_id
        assert len(session.scalars(select(ProcessedEvent)).all()) == 1
        records = session.scalars(select(RevenueEventRecord)).all()
        assert len(records) == 1
        assert records[0].normalized_payload["currency"] == "INR"
        replayed = service.replay("merchant_1", "evt_1")
        assert replayed.duplicate is True
        assert len(session.scalars(select(RevenueEventRecord)).all()) == 1
        assert (
            len(
                session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.event_type == "EVENT_DUPLICATE_RECEIVED"
                    )
                ).all()
            )
            == 2
        )


def test_failed_event_can_be_replayed_without_new_identity() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = EventIngestionService(session, "simulator")
        service.ingest(event("evt_failed"))
        service.mark_processing_failed("merchant_1", "evt_failed")
        replayed = service.replay("merchant_1", "evt_failed")

        assert replayed.duplicate is False
        assert replayed.status == "accepted"
        assert len(session.scalars(select(ProcessedEvent)).all()) == 1
        assert len(session.scalars(select(RevenueEventRecord)).all()) == 1


def test_webhook_rejects_bad_signature_before_persistence() -> None:
    get_settings().webhook_secret = "test-secret"
    response = TestClient(app).post(
        "/webhooks/simulator",
        content=event().model_dump_json(),
        headers={"X-Webhook-Signature": "sha256=invalid"},
    )
    assert response.status_code == 401


def test_webhook_accepts_signed_event_with_injected_session() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def session_dependency():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = session_dependency
    get_settings().webhook_secret = "test-secret"
    raw = event("evt_api").model_dump_json().encode()
    digest = hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()
    try:
        response = TestClient(app).post(
            "/webhooks/simulator",
            content=raw,
            headers={"X-Webhook-Signature": f"sha256={digest}"},
        )
        duplicate = TestClient(app).post(
            "/webhooks/simulator",
            content=raw,
            headers={"X-Webhook-Signature": f"sha256={digest}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["duplicate"] is False
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    with Session(engine) as session:
        cases = session.scalars(select(RecoveryCase)).all()
        assert len(cases) == 1
        assert cases[0].root_cause == "temporary_payment_failure"
        assert cases[0].expected_recoverable_amount is not None
        recommendations = session.scalars(select(Recommendation)).all()
        assert len(recommendations) == 1
        assert recommendations[0].source == "DETERMINISTIC_FALLBACK"


def test_signed_simulator_success_webhook_reconciles_once() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def session_dependency():
        with Session(engine) as session:
            yield session

    failed = event("evt-e2e-failed").model_copy(update={"payment_id": "pay-e2e"})
    succeeded = failed.model_copy(
        update={
            "event_id": "evt-e2e-succeeded",
            "event_type": RevenueEventType.PAYMENT_SUCCEEDED,
            "failure_code": None,
        }
    )
    app.dependency_overrides[get_db_session] = session_dependency
    get_settings().webhook_secret = "test-secret"
    try:
        client = TestClient(app)
        for payload in (failed, succeeded, succeeded):
            raw = payload.model_dump_json().encode()
            digest = hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()
            response = client.post(
                "/webhooks/simulator",
                content=raw,
                headers={"X-Webhook-Signature": f"sha256={digest}"},
            )
            assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()

    with Session(engine) as session:
        obligation = session.scalar(select(Obligation))
        attempt = session.scalar(select(PaymentAttempt))
        case = session.scalar(select(RecoveryCase))
        assert obligation is not None and obligation.authoritative_status == "paid"
        assert attempt is not None and attempt.status == "succeeded"
        assert case is not None and case.recovered_amount == 249900
        assert len(session.scalars(select(RevenueEventRecord)).all()) == 2


def test_webhook_opt_out_blocks_later_case_analysis_and_outreach() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def session_dependency():
        with Session(engine) as session:
            yield session

    opt_out = event("evt-api-opt-out").model_copy(
        update={
            "event_type": RevenueEventType.CUSTOMER_OPTED_OUT,
            "source_object_id": "preference-customer-1",
            "external_obligation_id": None,
            "obligation_type": None,
            "customer_external_id": "customer-1",
            "payment_id": None,
            "amount_minor_units": None,
            "currency": None,
            "payment_method": None,
            "failure_code": None,
        }
    )
    failure = event("evt-api-after-opt-out").model_copy(
        update={"customer_external_id": "customer-1"}
    )
    app.dependency_overrides[get_db_session] = session_dependency
    get_settings().webhook_secret = "test-secret"
    try:
        for payload in (opt_out, failure):
            raw = payload.model_dump_json().encode()
            digest = hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()
            response = TestClient(app).post(
                "/webhooks/simulator",
                content=raw,
                headers={"X-Webhook-Signature": f"sha256={digest}"},
            )
            assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()

    with Session(engine) as session:
        customer = session.scalar(select(Customer))
        case = session.scalar(select(RecoveryCase))
        assert customer is not None and customer.opted_out_at is not None
        assert case is not None and case.status == RecoveryCaseStatus.OPTED_OUT
        assert session.scalars(select(Recommendation)).all() == []
