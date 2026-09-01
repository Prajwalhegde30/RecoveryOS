"""Create the local-only merchant, admin, and active policy for the demo database."""

import os
from datetime import time, timedelta

from sqlalchemy import select

from app.auth.service import create_local_demo_token
from app.persistence.base import build_engine, build_session_factory
from app.persistence.models import (
    Merchant,
    MerchantMembership,
    MerchantPolicy,
    PolicyVersion,
    Role,
    User,
)
from app.policy.schema import ActionType, Channel, MerchantPolicyDocument, policy_json


def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    merchant_id = os.getenv("DEMO_MERCHANT_ID", "demo-merchant")
    subject = os.getenv("DEMO_USER_SUBJECT", "demo-user")
    secret = os.environ["DEMO_AUTH_SECRET"]
    engine = build_engine(database_url)
    factory = build_session_factory(engine)
    with factory.begin() as session:
        merchant = session.get(Merchant, merchant_id)
        if merchant is None:
            merchant = Merchant(
                id=merchant_id,
                external_key=f"demo:{merchant_id}",
                name="RecoveryOS Demo Merchant",
                default_currency="INR",
                timezone="Asia/Kolkata",
                environment_mode="simulator",
                status="active",
            )
            session.add(merchant)
            session.flush()

        user = session.scalar(select(User).where(User.subject == subject))
        if user is None:
            user = User(
                subject=subject,
                issuer="recoveryos-local",
                email_or_label="RecoveryOS demo admin",
                status="active",
            )
            session.add(user)
            session.flush()
        membership = session.get(MerchantMembership, (merchant_id, user.id))
        if membership is None:
            session.add(
                MerchantMembership(
                    merchant_id=merchant_id,
                    user_id=user.id,
                    role=Role.ADMIN,
                )
            )

        policy = session.scalar(
            select(PolicyVersion)
            .where(PolicyVersion.merchant_id == merchant_id, PolicyVersion.status == "ACTIVE")
            .limit(1)
        )
        if policy is None:
            document = MerchantPolicyDocument(
                timezone="Asia/Kolkata",
                max_attempts=3,
                min_contact_interval_minutes=30,
                quiet_hours_start=time(22, 0),
                quiet_hours_end=time(7, 0),
                approval_threshold_minor_units=100000000,
                max_contacts_per_case=3,
                max_contacts_per_customer=5,
                sequence_duration_minutes=240,
                enabled_channels={Channel.EMAIL, Channel.SMS},
                retry_max_attempts=3,
                incident_suppression_enabled=True,
                fallback_action=ActionType.SEND_EMAIL,
            )
            policy = PolicyVersion(
                merchant_id=merchant_id,
                version=1,
                policy_json=policy_json(document),
                created_by=subject,
                status="ACTIVE",
            )
            session.add(policy)
            session.flush()
            session.add(MerchantPolicy(merchant_id=merchant_id, current_version_id=policy.id))

    token = create_local_demo_token(
        subject=subject,
        issuer="recoveryos-local",
        merchant_id=merchant_id,
        role="ADMIN",
        secret=secret,
        audience="recoveryos-api",
        lifetime=timedelta(hours=8),
    )
    print(token)


if __name__ == "__main__":
    main()
