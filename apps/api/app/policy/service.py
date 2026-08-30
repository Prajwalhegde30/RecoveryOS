from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.persistence.models import AuditEvent, MerchantPolicy, PolicyVersion
from app.policy.schema import (
    MerchantPolicyDocument,
    PolicyVersionStatus,
    policy_from_json,
    policy_json,
)


class PolicyService:
    """Owns versioned merchant policy lifecycle; it does not evaluate actions."""

    def __init__(self, session: Session, merchant_id: str) -> None:
        self.session = session
        self.merchant_id = merchant_id

    def create_draft(self, policy: MerchantPolicyDocument, *, actor_id: str) -> PolicyVersion:
        if not actor_id:
            raise ValueError("actor_id is required")
        with self.session.begin():
            latest = self.session.scalar(
                select(func.max(PolicyVersion.version)).where(
                    PolicyVersion.merchant_id == self.merchant_id
                )
            )
            version = PolicyVersion(
                merchant_id=self.merchant_id,
                version=(latest or 0) + 1,
                policy_json=policy_json(policy),
                created_by=actor_id,
                status=PolicyVersionStatus.DRAFT,
            )
            self.session.add(version)
            self.session.flush()
            return version

    def activate(self, version_id: str, *, actor_id: str) -> PolicyVersion:
        if not actor_id:
            raise ValueError("actor_id is required")
        with self.session.begin():
            version = self.session.scalar(
                select(PolicyVersion)
                .where(
                    PolicyVersion.id == version_id,
                    PolicyVersion.merchant_id == self.merchant_id,
                )
                .with_for_update()
            )
            if version is None:
                raise LookupError("policy version not found")
            if version.status == PolicyVersionStatus.ACTIVE:
                return version
            if version.status != PolicyVersionStatus.DRAFT:
                raise ValueError("only a draft policy can be activated")
            policy = policy_from_json(version.policy_json)
            profile = self.session.scalar(
                select(MerchantPolicy)
                .where(MerchantPolicy.merchant_id == self.merchant_id)
                .with_for_update()
            )
            if profile is None:
                profile = MerchantPolicy(
                    merchant_id=self.merchant_id,
                    current_version_id=version.id,
                )
                self.session.add(profile)
            else:
                previous = self.session.scalar(
                    select(PolicyVersion).where(PolicyVersion.id == profile.current_version_id)
                )
                if previous is not None:
                    previous.status = PolicyVersionStatus.SUPERSEDED
                profile.current_version_id = version.id
            version.status = PolicyVersionStatus.ACTIVE
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="policy_version",
                    entity_id=version.id,
                    event_type="POLICY_ACTIVATED",
                    actor_type="admin",
                    actor_id=actor_id,
                    reason="validated merchant policy activated",
                    metadata_safe_json={
                        "version": version.version,
                        "timezone": policy.timezone,
                    },
                    correlation_id="policy-activation",
                )
            )
            return version

    def active(self) -> tuple[PolicyVersion, MerchantPolicyDocument] | None:
        with self.session.begin():
            profile = self.session.scalar(
                select(MerchantPolicy).where(MerchantPolicy.merchant_id == self.merchant_id)
            )
            if profile is None or profile.current_version_id is None:
                return None
            version = self.session.scalar(
                select(PolicyVersion).where(
                    PolicyVersion.id == profile.current_version_id,
                    PolicyVersion.merchant_id == self.merchant_id,
                )
            )
            if version is None or version.status != PolicyVersionStatus.ACTIVE:
                raise ValueError("merchant policy pointer is not active")
            return version, policy_from_json(version.policy_json)
