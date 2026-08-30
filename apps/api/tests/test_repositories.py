from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.persistence.base import Base
from app.persistence.models import Merchant, Obligation, RecoveryAction, RecoveryCase, ScheduledJob
from app.persistence.repositories import (
    RecoveryActionRepository,
    RecoveryCaseRepository,
    ScheduledJobRepository,
)


def make_session() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_recovery_case_repository_is_tenant_scoped() -> None:
    sessions = make_session()
    with sessions.begin() as session:
        merchant_a = Merchant(
            external_key="merchant_a",
            name="A",
            default_currency="INR",
            timezone="Asia/Kolkata",
            environment_mode="test",
            status="active",
        )
        merchant_b = Merchant(
            external_key="merchant_b",
            name="B",
            default_currency="INR",
            timezone="Asia/Kolkata",
            environment_mode="test",
            status="active",
        )
        session.add_all([merchant_a, merchant_b])
        session.flush()
        obligation = Obligation(
            merchant_id=merchant_a.id,
            obligation_type="payment",
            external_obligation_id="order_a",
            amount_at_risk=100,
            currency="INR",
            status="open",
            authoritative_status="failed",
        )
        session.add(obligation)
        session.flush()
        case = RecoveryCase(
            merchant_id=merchant_a.id,
            obligation_id=obligation.id,
            source_type="payment_failure",
            status="open",
            max_attempts_snapshot=1,
            currency="INR",
            attribution_status="pending",
        )
        session.add(case)
        session.flush()

        assert RecoveryCaseRepository(session, merchant_a.id).get(case.id) is case
        assert RecoveryCaseRepository(session, merchant_b.id).get(case.id) is None
        with pytest.raises(ValueError):
            RecoveryCaseRepository(session, merchant_b.id).add(case)


def test_job_claim_is_scoped_and_increments_attempt() -> None:
    sessions = make_session()
    with sessions.begin() as session:
        merchant = Merchant(
            external_key="merchant_jobs",
            name="Jobs",
            default_currency="INR",
            timezone="Asia/Kolkata",
            environment_mode="test",
            status="active",
        )
        session.add(merchant)
        session.flush()
        now = datetime(2026, 1, 1)
        job = ScheduledJob(
            merchant_id=merchant.id,
            job_type="send_retry_link",
            status="PENDING",
            due_at=now - timedelta(minutes=1),
            max_attempts=3,
            idempotency_key="job-1",
            correlation_id="corr-1",
        )
        session.add(job)
        session.flush()

        claimed = ScheduledJobRepository(session, merchant.id).claim_due(
            now, now + timedelta(minutes=5)
        )
        assert claimed is job
        assert job.status == "CLAIMED"
        assert job.attempt_count == 1
        assert job.lease_until == now + timedelta(minutes=5)


def test_action_idempotency_lookup_is_tenant_scoped() -> None:
    sessions = make_session()
    with sessions.begin() as session:
        merchant = Merchant(
            external_key="merchant_actions",
            name="Actions",
            default_currency="INR",
            timezone="Asia/Kolkata",
            environment_mode="test",
            status="active",
        )
        session.add(merchant)
        session.flush()
        action = RecoveryAction(
            merchant_id=merchant.id,
            recovery_case_id="case-1",
            action_type="send_retry_link",
            status="pending",
            idempotency_key="action-1",
            attempt_number=1,
            cost_minor_units=0,
            correlation_id="corr-1",
        )
        session.add(action)
        session.flush()

        repository = RecoveryActionRepository(session, merchant.id)
        assert repository.by_idempotency_key("action-1") is action
        assert repository.page(limit=500) == [action]
