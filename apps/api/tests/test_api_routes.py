import hashlib
import hmac
from collections.abc import Generator
from datetime import UTC, datetime, time, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.ai.contracts import ActionType
from app.api.dependencies import get_db_session
from app.auth.service import create_local_demo_token
from app.config import get_settings
from app.events.contracts import RevenueEvent, RevenueEventType
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
    WorkerHeartbeat,
)
from app.policy.schema import Channel, MerchantPolicyDocument
from app.policy.service import PolicyService

MERCHANT_ID = "merchant-api"
OTHER_MERCHANT_ID = "merchant-other"


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
        Merchant(
            id=OTHER_MERCHANT_ID,
            external_key="other-api-merchant",
            name="Other API Merchant",
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
    session.add(
        User(
            id="user-other-api",
            subject="subject-other-api",
            issuer="recoveryos-local",
            email_or_label="other@test",
            status="active",
        )
    )
    session.add(
        MerchantMembership(merchant_id=OTHER_MERCHANT_ID, user_id="user-other-api", role="ADMIN")
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


def other_merchant_headers() -> dict[str, str]:
    return auth_headers_for("subject-other-api", merchant_id=OTHER_MERCHANT_ID, role="ADMIN")


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
        operational_metrics = client.get("/api/v1/health/metrics", headers=auth_headers())
        assert operational_metrics.status_code == 200
        assert operational_metrics.json()["metrics"]["cases_total"] == 1
        assert operational_metrics.json()["metrics"]["events_received"] == 0
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
            client.get("/api/v1/cases/case-api", headers=other_merchant_headers()).status_code
            == 404
        )
        assert (
            client.get("/api/v1/policies/current", headers=other_merchant_headers()).status_code
            == 404
        )
        assert (
            client.get("/api/v1/health/operational", headers=other_merchant_headers()).json()[
                "merchant_id"
            ]
            == OTHER_MERCHANT_ID
        )
        other_metrics = client.get("/api/v1/health/metrics", headers=other_merchant_headers())
        assert other_metrics.status_code == 200
        assert other_metrics.json()["merchant_id"] == OTHER_MERCHANT_ID
        assert other_metrics.json()["metrics"]["cases_total"] == 0
        other_dashboard = client.get("/api/v1/dashboard", headers=other_merchant_headers())
        assert other_dashboard.status_code == 200
        assert other_dashboard.json()["metrics"]["revenue_at_risk_minor_units"] == 0
        assert client.get("/api/v1/cases", headers=other_merchant_headers()).json() == []
        assert client.get("/api/v1/incidents", headers=other_merchant_headers()).json() == []
        action = client.post(
            "/api/v1/cases/case-api/actions",
            json={
                "action_type": "GENERATE_PAYMENT_LINK",
                "idempotency_key": "cross-tenant-action",
                "due_at": "2030-01-01T12:00:00Z",
            },
            headers=other_merchant_headers(),
        )
        assert action.status_code == 404
    finally:
        app.dependency_overrides.clear()
        settings.auth_hmac_secret = previous_auth_secret
        session.close()


def test_versioned_routes_require_explicit_tenant_scope() -> None:
    response = TestClient(app).get("/api/v1/cases")
    assert response.status_code == 401


def test_operational_health_marks_stale_worker_heartbeat_degraded() -> None:
    session = make_session()
    session.add(
        WorkerHeartbeat(
            merchant_id=MERCHANT_ID,
            worker_id="worker-stale",
            status="healthy",
            last_seen_at=datetime.now(UTC) - timedelta(minutes=10),
            detail_safe="worker loop active",
        )
    )
    session.commit()

    def session_dependency() -> Generator[Session, None, None]:
        yield from override_session(session)

    app.dependency_overrides[get_db_session] = session_dependency
    settings = get_settings()
    previous_auth_secret = settings.auth_hmac_secret
    settings.auth_hmac_secret = "test-secret"
    try:
        response = TestClient(app).get("/api/v1/health/operational", headers=auth_headers())
        assert response.status_code == 200
        assert response.json()["components"]["worker"]["status"] == "degraded"
        assert response.json()["components"]["worker"]["detail"] == "worker heartbeat is stale"
    finally:
        app.dependency_overrides.clear()
        settings.auth_hmac_secret = previous_auth_secret
        session.close()


def test_generated_openapi_keeps_core_contract_paths() -> None:
    document = TestClient(app).get("/openapi.json")
    assert document.status_code == 200
    paths = document.json()["paths"]
    assert "/api/v1/dashboard" in paths
    assert "/api/v1/cases" in paths
    assert "/api/v1/cases/{case_id}/actions" in paths
    assert "/api/v1/cases/{case_id}/approvals" in paths
    assert "/api/v1/approvals" in paths
    assert "/api/v1/health/metrics" in paths
    assert "/webhooks/{provider}" in paths


def test_authenticated_signed_event_to_reconciled_dashboard_vertical_slice() -> None:
    session = make_session()
    failed = RevenueEvent(
        event_id="evt-vertical-failed",
        event_type=RevenueEventType.PAYMENT_FAILED,
        merchant_id=MERCHANT_ID,
        source_object_id="order-vertical",
        external_obligation_id="order-vertical",
        obligation_type="payment",
        payment_id="pay-vertical",
        payment_method="upi",
        failure_code="UPI_TIMEOUT",
        amount_minor_units=249900,
        currency="INR",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    succeeded = failed.model_copy(
        update={
            "event_id": "evt-vertical-succeeded",
            "event_type": RevenueEventType.PAYMENT_SUCCEEDED,
            "failure_code": None,
        }
    )

    def session_dependency() -> Generator[Session, None, None]:
        yield from override_session(session)

    app.dependency_overrides[get_db_session] = session_dependency
    settings = get_settings()
    previous_auth_secret = settings.auth_hmac_secret
    previous_webhook_secret = settings.webhook_secret
    settings.auth_hmac_secret = "test-secret"
    settings.webhook_secret = "webhook-secret"
    client = TestClient(app)

    def post_event(payload: RevenueEvent) -> None:
        session.rollback()
        raw = payload.model_dump_json().encode()
        digest = hmac.new(b"webhook-secret", raw, hashlib.sha256).hexdigest()
        response = client.post(
            "/webhooks/simulator",
            content=raw,
            headers={"X-Webhook-Signature": f"sha256={digest}"},
        )
        assert response.status_code == 200

    try:
        before = client.get("/api/v1/dashboard", headers=auth_headers()).json()["metrics"]
        post_event(failed)
        after_failure = client.get("/api/v1/dashboard", headers=auth_headers())
        assert after_failure.status_code == 200
        assert (
            after_failure.json()["metrics"]["revenue_at_risk_minor_units"]
            >= before["revenue_at_risk_minor_units"] + 249900
        )
        post_event(succeeded)
        after_success = client.get("/api/v1/dashboard", headers=auth_headers())
        assert after_success.status_code == 200
        assert (
            after_success.json()["metrics"]["recovered_minor_units"]
            >= before["recovered_minor_units"] + 249900
        )
        post_event(succeeded)
        duplicate_success = client.get("/api/v1/dashboard", headers=auth_headers())
        assert duplicate_success.json()["metrics"]["recovered_minor_units"] == after_success.json()[
            "metrics"
        ]["recovered_minor_units"]
    finally:
        app.dependency_overrides.clear()
        settings.auth_hmac_secret = previous_auth_secret
        settings.webhook_secret = previous_webhook_secret
        session.close()


def test_jwks_mode_does_not_fall_back_to_local_hmac() -> None:
    settings = get_settings()
    previous_mode = settings.auth_mode
    previous_jwks_url = settings.auth_jwks_url
    previous_auth_secret = settings.auth_hmac_secret
    settings.auth_mode = "jwks"
    settings.auth_jwks_url = None
    settings.auth_hmac_secret = "test-secret"
    try:
        response = TestClient(app).get("/api/v1/cases", headers=auth_headers())
        assert response.status_code == 503
        assert response.json()["detail"] == "authentication is not configured"
    finally:
        settings.auth_mode = previous_mode
        settings.auth_jwks_url = previous_jwks_url
        settings.auth_hmac_secret = previous_auth_secret


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
        evaluation_audit = session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "ACTION_REQUEST_EVALUATED")
        )
        assert evaluation_audit is not None
        assert evaluation_audit.metadata_safe_json["effective_role"] == "ADMIN"
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
        approvals = client.get("/api/v1/approvals", headers=auth_headers())
        assert approvals.status_code == 200
        assert approvals.json()[0]["case_id"] == "case-api"
        assert (
            client.get("/api/v1/approvals", headers=other_merchant_headers()).json() == []
        )
        policy_version_id = session.query(PolicyVersion).one().id
        viewer_approval = client.post(
            "/api/v1/cases/case-api/approvals",
            json={
                "policy_version_id": policy_version_id,
                "approved": True,
                "reason": "viewer must not approve",
            },
            headers=auth_headers_for("subject-viewer", role="VIEWER"),
        )
        assert viewer_approval.status_code == 403
        approved = client.post(
            "/api/v1/cases/case-api/approvals",
            json={
                "policy_version_id": policy_version_id,
                "approved": True,
                "reason": "approved by merchant administrator",
            },
            headers=auth_headers(),
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "ALLOW"
    finally:
        app.dependency_overrides.clear()
        settings.auth_hmac_secret = previous_auth_secret
        session.close()
