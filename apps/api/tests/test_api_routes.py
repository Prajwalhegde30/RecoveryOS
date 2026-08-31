from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db_session
from app.main import app
from app.persistence.base import Base
from app.persistence.models import (
    AuditEvent,
    CaseIncident,
    Incident,
    Merchant,
    Obligation,
    RecoveryCase,
    RecoveryCaseStatus,
)

MERCHANT_ID = "merchant-api"


def make_session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(
        Merchant(
            id=MERCHANT_ID,
            external_key="api-merchant",
            name="API Merchant",
            default_currency="INR",
            timezone="UTC",
            environment_mode="test",
            status="active",
        )
    )
    obligation = Obligation(
        id="obligation-api",
        merchant_id=MERCHANT_ID,
        obligation_type="payment",
        external_obligation_id="order-api",
        amount_at_risk=2500,
        currency="INR",
        status="open",
        authoritative_status="unpaid",
    )
    session.add(
        RecoveryCase(
            id="case-api",
            merchant_id=MERCHANT_ID,
            obligation_id=obligation.id,
            source_type="payment_failure",
            status=RecoveryCaseStatus.WAITING,
            max_attempts_snapshot=3,
            recovered_amount=0,
            currency="INR",
            attribution_status="pending",
            expected_recoverable_amount=1500,
            priority_score=80,
        )
    )
    incident = Incident(
        id="incident-api",
        merchant_id=MERCHANT_ID,
        dimension_key="payment_method:upi",
        status="OPEN",
        baseline_window={"failure_rate_percent": 5},
        current_window={"failure_rate_percent": 80},
        confidence=75,
        evidence_json={"source": "test"},
        detector_version="test-v1",
    )
    session.add_all([obligation, incident])
    session.flush()
    session.add(
        CaseIncident(
            incident_id=incident.id,
            recovery_case_id="case-api",
            association_reason="test association",
        )
    )
    session.add(
        AuditEvent(
            merchant_id=MERCHANT_ID,
            entity_type="recovery_case",
            entity_id="case-api",
            event_type="CASE_CREATED",
            actor_type="system",
            reason="test case",
            metadata_safe_json={},
            correlation_id="api-test",
        )
    )
    session.commit()
    return session


def override_session(session: Session) -> Generator[Session, None, None]:
    yield session


def test_versioned_read_routes_are_typed_and_tenant_scoped() -> None:
    session = make_session()

    def session_dependency() -> Generator[Session, None, None]:
        yield from override_session(session)

    app.dependency_overrides[get_db_session] = session_dependency
    client = TestClient(app)
    try:
        dashboard = client.get("/api/v1/dashboard", headers={"X-Merchant-Id": MERCHANT_ID})
        assert dashboard.status_code == 200
        cases = client.get("/api/v1/cases", headers={"X-Merchant-Id": MERCHANT_ID})
        assert cases.status_code == 200
        assert cases.json()[0]["amount_at_risk_minor_units"] == 2500
        detail = client.get("/api/v1/cases/case-api", headers={"X-Merchant-Id": MERCHANT_ID})
        assert detail.status_code == 200
        assert detail.json()["timeline"][0]["event_type"] == "CASE_CREATED"
        incidents = client.get("/api/v1/incidents", headers={"X-Merchant-Id": MERCHANT_ID})
        assert incidents.status_code == 200
        assert incidents.json()[0]["affected_case_ids"] == ["case-api"]
        assert (
            client.get(
                "/api/v1/cases/case-api", headers={"X-Merchant-Id": "other-merchant"}
            ).status_code
            == 404
        )
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_versioned_routes_require_explicit_tenant_scope() -> None:
    response = TestClient(app).get("/api/v1/cases")
    assert response.status_code == 401
