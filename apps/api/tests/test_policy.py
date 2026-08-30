import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.ai.contracts import ActionType
from app.persistence.base import Base
from app.persistence.models import AuditEvent, PolicyVersion
from app.policy.schema import Channel, MerchantPolicyDocument, PolicyVersionStatus
from app.policy.service import PolicyService


def policy() -> MerchantPolicyDocument:
    return MerchantPolicyDocument(
        timezone="Asia/Kolkata",
        max_attempts=3,
        min_contact_interval_minutes=240,
        quiet_hours_start="21:00",
        quiet_hours_end="08:00",
        approval_threshold_minor_units=5_000_000,
        max_contacts_per_case=3,
        max_contacts_per_customer=5,
        sequence_duration_minutes=1_440,
        enabled_channels={Channel.EMAIL, Channel.SMS},
        retry_max_attempts=3,
        incident_suppression_enabled=True,
        fallback_action=ActionType.WAIT,
    )


def test_policy_document_rejects_invalid_values_and_unknown_fields() -> None:
    with pytest.raises(ValueError, match="timezone"):
        policy_data = policy().model_dump()
        policy_data["timezone"] = "Not/AZone"
        MerchantPolicyDocument.model_validate(policy_data)

    with pytest.raises(ValueError, match="greater than or equal to 0"):
        policy_data = policy().model_dump()
        policy_data["approval_threshold_minor_units"] = -1
        MerchantPolicyDocument.model_validate(policy_data)

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        policy_data = policy().model_dump()
        policy_data["unbounded_retry"] = True
        MerchantPolicyDocument.model_validate(policy_data)


def test_policy_versions_are_tenant_scoped_immutable_history_with_active_pointer() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = PolicyService(session, "merchant_policy")
        first = service.create_draft(policy(), actor_id="admin-1")
        first_id = first.id
        session.rollback()
        active = service.activate(first_id, actor_id="admin-1")
        assert active.status == PolicyVersionStatus.ACTIVE
        session.rollback()
        current = service.active()
        assert current is not None
        assert current[0].id == first_id
        assert current[1].timezone == "Asia/Kolkata"
        session.rollback()

        second = service.create_draft(
            policy().model_copy(update={"max_attempts": 5}), actor_id="admin-1"
        )
        second_id = second.id
        session.rollback()
        service.activate(second_id, actor_id="admin-1")
        session.rollback()
        versions = session.scalars(
            select(PolicyVersion).where(PolicyVersion.merchant_id == "merchant_policy")
        ).all()
        assert sorted(version.version for version in versions) == [1, 2]
        assert {version.status for version in versions} == {
            PolicyVersionStatus.SUPERSEDED,
            PolicyVersionStatus.ACTIVE,
        }
        audits = session.scalars(
            select(AuditEvent).where(
                AuditEvent.merchant_id == "merchant_policy",
                AuditEvent.event_type == "POLICY_ACTIVATED",
            )
        ).all()
        assert len(audits) == 2

        session.rollback()
        with pytest.raises(LookupError, match="not found"):
            PolicyService(session, "other_merchant").activate(first_id, actor_id="admin-2")


def test_policy_activation_rejects_superseded_version() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = PolicyService(session, "merchant_policy")
        first = service.create_draft(policy(), actor_id="admin-1")
        first_id = first.id
        session.rollback()
        service.activate(first_id, actor_id="admin-1")
        session.rollback()
        second = service.create_draft(
            policy().model_copy(update={"max_attempts": 4}), actor_id="admin-1"
        )
        second_id = second.id
        session.rollback()
        service.activate(second_id, actor_id="admin-1")
        session.rollback()
        with pytest.raises(ValueError, match="only a draft"):
            service.activate(first_id, actor_id="admin-1")
