from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.cases.lifecycle import CaseLifecycleService
from app.cases.service import RecoveryCaseService
from app.cases.state_machine import ActorType, TransitionError
from app.events.contracts import RevenueEvent
from app.events.service import EventIngestionService
from app.persistence.base import Base
from app.persistence.models import AuditEvent, RecoveryCase, RecoveryCaseStatus


def make_case_session() -> tuple[Session, str]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    event = RevenueEvent(
        event_id="evt_state",
        event_type="payment.failed",
        merchant_id="merchant_state",
        source_object_id="order_state",
        amount_minor_units=1000,
        currency="INR",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    EventIngestionService(session, "simulator").ingest(event)
    case = RecoveryCaseService(session, "simulator", 3).associate(event)
    assert case is not None
    case_id = case.id
    session.rollback()
    return session, case_id


def transition(service: CaseLifecycleService, case_id: str, target: RecoveryCaseStatus) -> None:
    service.transition(
        case_id,
        target,
        actor_type=ActorType.SYSTEM,
        reason="state machine test",
        correlation_id="corr-state",
    )
    service.session.rollback()


def test_typical_state_machine_path_is_audited() -> None:
    session, case_id = make_case_session()
    service = CaseLifecycleService(session, "merchant_state")
    for target in [
        RecoveryCaseStatus.ANALYZING,
        RecoveryCaseStatus.ACTION_PENDING,
        RecoveryCaseStatus.POLICY_CHECK,
        RecoveryCaseStatus.SCHEDULED,
        RecoveryCaseStatus.ACTION_EXECUTED,
        RecoveryCaseStatus.WAITING,
        RecoveryCaseStatus.RECOVERED,
    ]:
        transition(service, case_id, target)

    assert len(service.history(case_id)) == 8
    assert session.scalar(select(func.count()).select_from(AuditEvent)) == 8


def test_illegal_transition_does_not_mutate_case_or_audit() -> None:
    session, case_id = make_case_session()
    service = CaseLifecycleService(session, "merchant_state")
    with pytest.raises(TransitionError):
        service.transition(
            case_id,
            RecoveryCaseStatus.ACTION_EXECUTED,
            actor_type=ActorType.SYSTEM,
            reason="invalid",
            correlation_id="corr-invalid",
        )
    session.rollback()
    case = session.get(RecoveryCase, case_id)
    assert case is not None
    assert case.status == RecoveryCaseStatus.DETECTED
    assert session.scalar(select(func.count()).select_from(AuditEvent)) == 1


@pytest.mark.parametrize(
    "target",
    [
        RecoveryCaseStatus.RECOVERED,
        RecoveryCaseStatus.OPTED_OUT,
        RecoveryCaseStatus.CANCELLED,
        RecoveryCaseStatus.EXHAUSTED,
    ],
)
def test_terminal_case_rejects_customer_facing_progression(target: RecoveryCaseStatus) -> None:
    session, case_id = make_case_session()
    service = CaseLifecycleService(session, "merchant_state")
    transition(service, case_id, target)
    with pytest.raises(TransitionError):
        service.transition(
            case_id,
            RecoveryCaseStatus.ACTION_PENDING,
            actor_type=ActorType.SYSTEM,
            reason="must be rejected",
            correlation_id="corr-terminal",
        )
