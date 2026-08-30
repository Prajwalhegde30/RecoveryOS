from datetime import UTC, datetime
from time import sleep

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.ai.contracts import ActionType, RecommendationEvidence, RecommendationOutput
from app.ai.factory import configured_ai_provider
from app.ai.fallback import deterministic_fallback
from app.ai.provider import (
    AIOutputValidationError,
    AITimeoutError,
    AITransportError,
    ProviderAdapter,
    StaticAIProvider,
)
from app.ai.service import AIRecommendationService
from app.cases.service import RecoveryCaseService
from app.events.contracts import RevenueEvent
from app.events.service import EventIngestionService
from app.persistence.base import Base
from app.persistence.models import AuditEvent, Recommendation
from app.scoring.economics import ScoringConfig
from app.scoring.service import CaseAnalysisService


def evidence() -> RecommendationEvidence:
    return RecommendationEvidence(
        source_type="payment.failed",
        root_cause="temporary_payment_failure",
        root_cause_confidence_percent=85,
        recovery_probability_percent=60,
        expected_recoverable_amount_minor_units=6000,
        priority_score=5100,
        payment_method="upi",
        failure_code="UPI_TIMEOUT",
        attempt_count=1,
        scoring_version="scoring-v1",
    )


def recommendation(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "action": "WAIT",
        "parameters": {"delay_minutes": 30},
        "reason_code": "TRANSIENT_FAILURE",
        "rationale": "Wait for the transient provider failure to clear before outreach.",
        "evidence": ["failure_code:UPI_TIMEOUT", "scoring_version:scoring-v1"],
        "confidence_percent": 85,
        "fallback_action": "SCHEDULE_RETRY",
        "prompt_version": "provider-version-ignored",
        "model_version": "provider-version-ignored",
        "schema_version": "provider-version-ignored",
    }
    value.update(overrides)
    return value


SYNTHETIC_EVALUATION_CASES = (
    ("temporary_payment_failure", ActionType.WAIT),
    ("insufficient_funds", ActionType.SCHEDULE_RETRY),
    ("expired_card", ActionType.REQUEST_PAYMENT_METHOD_UPDATE),
    ("checkout_abandonment", ActionType.GENERATE_PAYMENT_LINK),
    ("customer_cancellation", ActionType.STOP),
    ("unknown", ActionType.ESCALATE_TO_HUMAN),
)


def test_recommendation_contract_allows_registered_actions_only() -> None:
    output = RecommendationOutput.model_validate(recommendation())
    assert output.action == ActionType.WAIT

    with pytest.raises(ValueError, match="unsupported action parameters"):
        RecommendationOutput.model_validate(
            recommendation(action="SEND_EMAIL", parameters={"delay_minutes": 30})
        )

    with pytest.raises(ValueError, match="forbidden parameter keys"):
        RecommendationOutput.model_validate(
            recommendation(action="GENERATE_PAYMENT_LINK", parameters={"amount": 500})
        )

    with pytest.raises(ValueError, match="non-negative integer"):
        RecommendationOutput.model_validate(recommendation(parameters={"delay_minutes": "later"}))


def test_provider_adapter_minimizes_input_and_persists_configured_versions() -> None:
    captured: dict[str, object] = {}

    def transport(payload: dict[str, object]) -> object:
        captured.update(payload)
        return recommendation()

    provider = ProviderAdapter(
        transport,
        timeout_seconds=1,
        prompt_version="prompt-v2",
        model_version="model-v2",
    )
    output = provider.recommend(evidence())

    assert "merchant_id" not in captured
    assert "customer_email" not in captured
    assert output.prompt_version == "prompt-v2"
    assert output.model_version == "model-v2"
    assert output.schema_version == "recommendation-v1"


def test_provider_failures_are_typed_and_safe() -> None:
    with pytest.raises(AITransportError, match="request failed"):
        ProviderAdapter(
            lambda payload: 1 / 0,
            timeout_seconds=1,
            prompt_version="prompt-v1",
            model_version="model-v1",
        ).recommend(evidence())

    with pytest.raises(AITimeoutError, match="timed out"):
        ProviderAdapter(
            lambda payload: (sleep(0.05), recommendation())[1],
            timeout_seconds=0.001,
            prompt_version="prompt-v1",
            model_version="model-v1",
        ).recommend(evidence())


def test_ai_factory_selects_deterministic_fallback_or_validates_transport_mode() -> None:
    from app.config import Settings

    deterministic = Settings(ai_provider="deterministic")
    assert configured_ai_provider(deterministic) is None

    with pytest.raises(ValueError, match="requires an application-provided transport"):
        configured_ai_provider(
            Settings(ai_provider="transport", ai_timeout_ms=1000, ai_model="model")
        )

    provider = configured_ai_provider(
        Settings(ai_provider="transport", ai_timeout_ms=1000, ai_model="model"),
        transport=lambda payload: recommendation(),
    )
    assert provider is not None
    assert provider.recommend(evidence()).action == ActionType.WAIT

    with pytest.raises(AIOutputValidationError, match="invalid recommendation"):
        ProviderAdapter(
            lambda payload: recommendation(action="UNREGISTERED"),
            timeout_seconds=1,
            prompt_version="prompt-v1",
            model_version="model-v1",
        ).recommend(evidence())


def test_deterministic_fallback_is_registered_and_root_cause_specific() -> None:
    assert deterministic_fallback(evidence()).action == ActionType.WAIT
    assert (
        deterministic_fallback(evidence().model_copy(update={"root_cause": "expired_card"})).action
        == ActionType.REQUEST_PAYMENT_METHOD_UPDATE
    )
    assert (
        deterministic_fallback(evidence().model_copy(update={"root_cause": "unknown"})).action
        == ActionType.ESCALATE_TO_HUMAN
    )


def test_fixed_synthetic_evaluation_fixture_covers_fallback_actions() -> None:
    for root_cause, expected_action in SYNTHETIC_EVALUATION_CASES:
        assert (
            deterministic_fallback(evidence().model_copy(update={"root_cause": root_cause})).action
            == expected_action
        )


def test_ai_failure_uses_auditable_deterministic_fallback() -> None:
    provider = ProviderAdapter(
        lambda payload: 1 / 0,
        timeout_seconds=1,
        prompt_version="prompt-v1",
        model_version="model-v1",
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    event = RevenueEvent(
        event_id="evt_ai_fallback",
        event_type="payment.failed",
        merchant_id="merchant_fallback",
        source_object_id="order_fallback",
        amount_minor_units=10000,
        currency="INR",
        payment_method="upi",
        failure_code="UPI_TIMEOUT",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with Session(engine) as session:
        EventIngestionService(session, "simulator").ingest(event)
        case = RecoveryCaseService(session, "simulator", 3).associate(event)
        assert case is not None
        case_id = case.id
        session.rollback()
        CaseAnalysisService(
            session,
            "merchant_fallback",
            ScoringConfig(50, 10, 20, 50, "scoring-v1"),
        ).analyze(case_id)
        session.rollback()
        stored = AIRecommendationService(
            session, "merchant_fallback", provider
        ).recommend_with_fallback(case_id, minimum_confidence_percent=90)
        assert stored.source == "DETERMINISTIC_FALLBACK"
        assert stored.action_type == ActionType.WAIT
        session.rollback()
        fallback_audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_type == "recovery_case",
                AuditEvent.entity_id == case_id,
                AuditEvent.event_type == "AI_FALLBACK_USED",
            )
        )
        assert fallback_audit is not None


def test_ai_recommendation_persists_advisory_output_with_tenant_scope() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    event = RevenueEvent(
        event_id="evt_ai",
        event_type="payment.failed",
        merchant_id="merchant_ai",
        source_object_id="order_ai",
        amount_minor_units=10000,
        currency="INR",
        payment_method="upi",
        failure_code="UPI_TIMEOUT",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with Session(engine) as session:
        EventIngestionService(session, "simulator").ingest(event)
        case = RecoveryCaseService(session, "simulator", 3).associate(event)
        assert case is not None
        case_id = case.id
        session.rollback()
        CaseAnalysisService(
            session,
            "merchant_ai",
            ScoringConfig(50, 10, 20, 50, "scoring-v1"),
        ).analyze(case_id)
        session.rollback()

        provider = StaticAIProvider(RecommendationOutput.model_validate(recommendation()))
        stored = AIRecommendationService(session, "merchant_ai", provider).recommend(case_id)
        assert stored.action_type == ActionType.WAIT
        assert stored.source == "AI"
        assert stored.scoring_version == "scoring-v1"
        assert stored.prompt_version == "provider-version-ignored"

        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_type == "recommendation",
                AuditEvent.entity_id == stored.id,
            )
        )
        assert audit is not None
        assert audit.event_type == "RECOMMENDATION_CREATED"

        session.rollback()
        with pytest.raises(LookupError, match="not found"):
            AIRecommendationService(session, "other_merchant", provider).recommend(case_id)

        assert (
            session.scalar(select(Recommendation).where(Recommendation.id == stored.id)) is not None
        )
