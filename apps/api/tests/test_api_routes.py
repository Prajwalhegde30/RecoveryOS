from collections.abc import Generator
from datetime import UTC, datetime, time, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.ai.contracts import ActionType
from app.api.dependencies import get_db_session
from app.auth.service import create_local_demo_token
from app.config import get_settings
from app.main import app
from app.persistence.base import Base
from app.persistence.models import (
    AuditEvent,
    CaseIncident,
    Incident,
    Merchant,
    MerchantMembership,
    MerchantPolicy,
    Obligation,
    PolicyVersion,
    RecoveryCase,
    RecoveryCaseStatus,
    User,
)
from app.policy.schema import Channel, MerchantPolicyDocument
from app.policy.service import PolicyService

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
    session.add(
        User(
            id="user-api",
            subject="subject-api",
            issuer="recoveryos-local",
            email_or_label="api@test",
            status="active",
        )
    )
    session.add(MerchantMembership(merchant_id=MERCHANT_ID, user_id="user-api", role="ADMIN"))
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


def auth_headers(merchant_id: str = MERCHANT_ID) -> dict[str, str]:
    return auth_headers_for("subject-api", merchant_id=merchant_id)


def auth_headers_for(
    subject: str, *, merchant_id: str = MERCHANT_ID, role: str = "ADMIN"
) -> dict[str, str]:
    token = create_local_demo_token(
        subject=subject,
        issuer="recoveryos-local",
        merchant_id=merchant_id,
        role=role,
        secret="test-secret",
        audience="recoveryos-api",
        lifetime=timedelta(hours=1),
    )
    return {"Authorization": f"Bearer {token}"}


def activate_policy(session: Session, *, approval_threshold: int = 10_000) -> None:
    session.rollback()
    now = datetime.now(UTC)
    policy = MerchantPolicyDocument(
        timezone="UTC",
        max_attempts=3,
        min_contact_interval_minutes=0,
        quiet_hours_start=time((now.hour + 1) % 24),
        quiet_hours_end=time((now.hour + 2) % 24),
        approval_threshold_minor_units=approval_threshold,
        max_contacts_per_case=3,
        max_contacts_per_customer=3,
        sequence_duration_minutes=60,
        enabled_channels={Channel.EMAIL, Channel.SMS, Channel.WHATSAPP},
        retry_max_attempts=2,
        incident_suppression_enabled=True,
        fallback_action=ActionType.SEND_EMAIL,
    )
    version = PolicyService(session, MERCHANT_ID).create_draft(policy, actor_id="admin-api")
    version_id = version.id
    session.rollback()
    PolicyService(session, MERCHANT_ID).activate(version_id, actor_id="admin-api")


def test_versioned_read_routes_are_typed_and_tenant_scoped() -> None:
    session = make_session()

    def session_dependency() -> Generator[Session, None, None]:
        yield from override_session(session)

    app.dependency_overrides[get_db_session] = session_dependency
    settings = get_settings()
    previous_auth_secret = settings.auth_hmac_secret
    settings.auth_hmac_secret = "test-secret"
    client = TestClient(app)
    try:
        dashboard = client.get("/api/v1/dashboard", headers=auth_headers())
        assert dashboard.status_code == 200
        operational = client.get("/api/v1/health/operational", headers=auth_headers())
        assert operational.status_code == 200
        assert operational.json()["components"]["database"]["status"] == "healthy"
        cases = client.get("/api/v1/cases", headers=auth_headers())
        assert cases.status_code == 200
        assert cases.json()[0]["amount_at_risk_minor_units"] == 2500
        detail = client.get("/api/v1/cases/case-api", headers=auth_headers())
        assert detail.status_code == 200
        assert detail.json()["timeline"][0]["event_type"] == "CASE_CREATED"
        incidents = client.get("/api/v1/incidents", headers=auth_headers())
        assert incidents.status_code == 200
        assert incidents.json()[0]["affected_case_ids"] == ["case-api"]
        assert (
            client.get("/api/v1/cases/case-api", headers=auth_headers("other-merchant")).status_code
            == 403
        )
    finally:
        app.dependency_overrides.clear()
        settings.auth_hmac_secret = previous_auth_secret
        session.close()


def test_versioned_routes_require_explicit_tenant_scope() -> None:
    response = TestClient(app).get("/api/v1/cases")
    assert response.status_code == 401


def test_simulator_endpoint_reuses_seeded_event_identity() -> None:
    session = make_session()

    def session_dependency() -> Generator[Session, None, None]:
        yield from override_session(session)

    app.dependency_overrides[get_db_session] = session_dependency
    settings = get_settings()
    previous_auth_secret = settings.auth_hmac_secret
    settings.auth_hmac_secret = "test-secret"
    client = TestClient(app)
    payload = {
        "seed": 712,
        "transaction_count": 1,
        "amounts_minor_units": [1000],
        "payment_methods": ["upi"],
        "failure_codes": ["UPI_TIMEOUT"],
    }
    try:
        first = client.post(
            "/api/v1/simulator/runs",
            json=payload,
            headers=auth_headers(),
        )
        second = client.post(
            "/api/v1/simulator/runs",
            json=payload,
            headers=auth_headers(),
        )
        assert first.status_code == 200
        assert first.json()["label"] == "synthetic_simulator_data"
        assert second.status_code == 200
        assert second.json()["run_id"] == first.json()["run_id"]
        assert second.json()["status"] == "COMPLETED"
        status_response = client.get(
            f"/api/v1/simulator/runs/{first.json()['run_id']}", headers=auth_headers()
        )
        assert status_response.status_code == 200
        assert status_response.json()["case_ids"] == first.json()["case_ids"]
        reset = client.post(
            f"/api/v1/simulator/runs/{first.json()['run_id']}/reset",
            headers=auth_headers(),
        )
        assert reset.status_code == 200
        assert reset.json()["status"] == "RESET"
    finally:
        app.dependency_overrides.clear()
        settings.auth_hmac_secret = previous_auth_secret
        session.close()


def test_action_command_evaluates_policy_and_is_idempotent() -> None:
    session = make_session()
    activate_policy(session)

    def session_dependency() -> Generator[Session, None, None]:
        yield from override_session(session)

    app.dependency_overrides[get_db_session] = session_dependency
    settings = get_settings()
    previous_auth_secret = settings.auth_hmac_secret
    settings.auth_hmac_secret = "test-secret"
    client = TestClient(app)
    payload = {
        "action_type": "GENERATE_PAYMENT_LINK",
        "idempotency_key": "action-api-1",
        "due_at": "2030-01-01T12:00:00Z",
    }
    try:
        policy_response = client.get("/api/v1/policies/current", headers=auth_headers())
        assert policy_response.status_code == 200
        assert policy_response.json()["status"] == "ACTIVE"
        first = client.post("/api/v1/cases/case-api/actions", json=payload, headers=auth_headers())
        second = client.post("/api/v1/cases/case-api/actions", json=payload, headers=auth_headers())
        assert first.status_code == 200
        assert first.json()["status"] == "SCHEDULED"
        assert first.json()["job_id"] == second.json()["job_id"]
        assert session.query(PolicyVersion).count() == 1
        assert session.query(MerchantPolicy).count() == 1
    finally:
        app.dependency_overrides.clear()
        settings.auth_hmac_secret = previous_auth_secret
        session.close()


def test_action_command_requires_operator_role_and_persists_blocking_decision() -> None:
    session = make_session()
    activate_policy(session, approval_threshold=1_000)
    session.add(
        User(
            id="user-viewer",
            subject="subject-viewer",
            issuer="recoveryos-local",
            email_or_label="viewer@test",
            status="active",
        )
    )
    session.add(MerchantMembership(merchant_id=MERCHANT_ID, user_id="user-viewer", role="VIEWER"))
    session.commit()

    def session_dependency() -> Generator[Session, None, None]:
        yield from override_session(session)

    app.dependency_overrides[get_db_session] = session_dependency
    settings = get_settings()
    previous_auth_secret = settings.auth_hmac_secret
    settings.auth_hmac_secret = "test-secret"
    client = TestClient(app)
    payload = {
        "action_type": "SEND_EMAIL",
        "idempotency_key": "action-api-blocked",
        "due_at": "2030-01-01T12:00:00Z",
        "channel": "email",
    }
    try:
        forbidden = client.post(
            "/api/v1/cases/case-api/actions",
            json=payload,
            headers=auth_headers_for("subject-viewer", role="VIEWER"),
        )
        assert forbidden.status_code == 403
        blocked = client.post(
            "/api/v1/cases/case-api/actions", json=payload, headers=auth_headers()
        )
        assert blocked.status_code == 200
        assert blocked.json()["status"] == "REQUIRES_APPROVAL"
        assert blocked.json()["job_id"] is None
    finally:
        app.dependency_overrides.clear()
        settings.auth_hmac_secret = previous_auth_secret
        session.close()
