from datetime import UTC, datetime, time

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.ai.contracts import ActionType
from app.persistence.base import Base
from app.persistence.models import (
    AttributionRecord,
    Obligation,
    PaymentAttempt,
    Recommendation,
    RecoveryCase,
    RecoveryCaseStatus,
    RevenueEvent,
)
from app.policy.schema import Channel, MerchantPolicyDocument
from app.policy.service import PolicyService
from app.scoring.economics import ScoringConfig
from app.simulator.service import SimulatorConfig, SimulatorService


def simulator_config(seed: int = 42) -> SimulatorConfig:
    return SimulatorConfig(
        seed=seed,
        merchant_ids=("merchant_simulator", "merchant_simulator_2"),
        transaction_count=6,
        amounts_minor_units=(2_499, 19_999),
        payment_methods=("upi", "card"),
        failure_codes=("UPI_TIMEOUT", "CARD_DECLINED"),
        high_value_indices=frozenset({4}),
        high_value_amount_minor_units=250_000,
        duplicate_event_indices=frozenset({1}),
        opt_out_indices=frozenset({2}),
        incident_indices=frozenset({3}),
        natural_recovery_indices=frozenset({0}),
        assisted_recovery_indices=frozenset({5}),
        provider_failure_indices=frozenset({4}),
        scoring_config=ScoringConfig(50, 10, 20, 50, "scoring-v1"),
        max_recovery_attempts=3,
    )


def activate_simulator_policies(session: Session) -> None:
    now = datetime.now(UTC)
    for merchant_id in ("merchant_simulator", "merchant_simulator_2"):
        policy = MerchantPolicyDocument(
            timezone="UTC",
            max_attempts=3,
            min_contact_interval_minutes=0,
            quiet_hours_start=time((now.hour + 1) % 24),
            quiet_hours_end=time((now.hour + 2) % 24),
            approval_threshold_minor_units=10_000_000,
            max_contacts_per_case=3,
            max_contacts_per_customer=3,
            sequence_duration_minutes=60,
            enabled_channels={Channel.EMAIL},
            retry_max_attempts=2,
            incident_suppression_enabled=True,
            fallback_action=ActionType.SEND_EMAIL,
        )
        version = PolicyService(session, merchant_id).create_draft(policy, actor_id="simulator")
        version_id = version.id
        session.rollback()
        PolicyService(session, merchant_id).activate(version_id, actor_id="simulator")


def test_seeded_simulator_uses_normal_paths_and_reports_persisted_facts() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        SimulatorService(session, simulator_config())._ensure_merchants()
        activate_simulator_policies(session)
        result = SimulatorService(session, simulator_config()).run()

        assert result.label == "synthetic_simulator_data"
        assert result.persisted_event_count == 10
        assert result.duplicate_event_count == 1
        assert result.case_count == 6
        assert result.recommendation_count == 6
        assert result.success_event_count == 2
        assert result.scenario_counts == {
            "duplicate_event": 1,
            "high_value": 1,
            "incident": 1,
            "assisted_recovery": 1,
            "natural_recovery": 1,
            "opt_out": 1,
            "provider_failure": 1,
        }
        assert session.scalar(select(func.count()).select_from(RevenueEvent)) == 10
        assert session.scalar(select(func.count()).select_from(RecoveryCase)) == 6
        assert session.scalar(select(func.count()).select_from(PaymentAttempt)) == 6
        attributions = session.scalars(select(AttributionRecord)).all()
        assert len(attributions) == 6
        assert sum(record.outcome == "NATURAL_RECOVERY" for record in attributions) == 1
        assert sum(record.outcome == "ASSISTED_RECOVERY" for record in attributions) == 1
        assert sum(record.qualifying_action_id is not None for record in attributions) == 1
        assert session.scalar(select(func.count()).select_from(Recommendation)) == 6
        assert all(event.provider == "simulator" for event in session.scalars(select(RevenueEvent)))
        recovered_cases = session.scalars(
            select(RecoveryCase).where(RecoveryCase.status == RecoveryCaseStatus.RECOVERED)
        ).all()
        paid_obligations = session.scalars(
            select(Obligation).where(Obligation.authoritative_status == "paid")
        ).all()
        assert len(recovered_cases) == result.success_event_count
        assert len(paid_obligations) == result.success_event_count
        assert all(case.recovered_amount > 0 for case in recovered_cases)


def test_same_seed_reproduces_event_inputs_without_duplicate_domain_effects() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        SimulatorService(session, simulator_config())._ensure_merchants()
        activate_simulator_policies(session)
        first = SimulatorService(session, simulator_config()).run()
        session.rollback()
        second = SimulatorService(session, simulator_config()).run()

        assert first.event_ids == second.event_ids
        assert first.case_count == 6
        assert second.case_count == 0
        assert second.duplicate_event_count == 7
        assert session.scalar(select(func.count()).select_from(RevenueEvent)) == 10


def test_simulator_rejects_overlapping_or_out_of_range_scenarios() -> None:
    base = dict(
        seed=1,
        merchant_ids=("merchant",),
        transaction_count=2,
        amounts_minor_units=(100,),
        payment_methods=("upi",),
        failure_codes=("UPI_TIMEOUT",),
    )
    try:
        SimulatorConfig(
            **base,
            natural_recovery_indices=frozenset({0}),
            assisted_recovery_indices=frozenset({0}),
        )
    except ValueError as exc:
        assert "must not overlap" in str(exc)
    else:
        raise AssertionError("overlapping recovery scenarios must be rejected")

    try:
        SimulatorConfig(**base, duplicate_event_indices=frozenset({2}))
    except ValueError as exc:
        assert "within transaction_count" in str(exc)
    else:
        raise AssertionError("out-of-range scenarios must be rejected")
