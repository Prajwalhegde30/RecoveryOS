from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.persistence.models import (
    JobStatus,
    Obligation,
    PaymentAttempt,
    RecoveryAction,
    RecoveryCase,
    ScheduledJob,
)


class TenantRepository[ModelT]:
    """Base query boundary for models with a direct merchant_id column."""

    def __init__(self, session: Session, model: type[ModelT], merchant_id: str) -> None:
        self.session = session
        self.model = model
        self.merchant_id = merchant_id

    def scoped(self, statement: Select[tuple[ModelT]]) -> Select[tuple[ModelT]]:
        return statement.where(self.model.merchant_id == self.merchant_id)  # type: ignore[attr-defined]

    def get(self, entity_id: str) -> ModelT | None:
        statement = self.scoped(select(self.model).where(self.model.id == entity_id))  # type: ignore[attr-defined]
        return self.session.scalar(statement)

    def add(self, entity: ModelT) -> ModelT:
        if getattr(entity, "merchant_id", None) != self.merchant_id:
            raise ValueError("entity merchant scope does not match repository scope")
        self.session.add(entity)
        return entity

    def page(self, limit: int = 50, offset: int = 0) -> list[ModelT]:
        safe_limit = min(max(limit, 1), 100)
        safe_offset = max(offset, 0)
        statement = self.scoped(select(self.model).offset(safe_offset).limit(safe_limit))
        return list(self.session.scalars(statement).all())


class ObligationRepository(TenantRepository[Obligation]):
    def __init__(self, session: Session, merchant_id: str) -> None:
        super().__init__(session, Obligation, merchant_id)

    def by_identity(self, obligation_type: str, external_id: str) -> Obligation | None:
        statement = self.scoped(
            select(Obligation).where(
                Obligation.obligation_type == obligation_type,
                Obligation.external_obligation_id == external_id,
            )
        )
        return self.session.scalar(statement)


class RecoveryCaseRepository(TenantRepository[RecoveryCase]):
    def __init__(self, session: Session, merchant_id: str) -> None:
        super().__init__(session, RecoveryCase, merchant_id)

    def by_obligation(self, obligation_id: str, *, for_update: bool = False) -> RecoveryCase | None:
        statement = self.scoped(
            select(RecoveryCase).where(RecoveryCase.obligation_id == obligation_id)
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)


class PaymentAttemptRepository(TenantRepository[PaymentAttempt]):
    def __init__(self, session: Session, merchant_id: str) -> None:
        super().__init__(session, PaymentAttempt, merchant_id)

    def by_provider_identity(
        self, provider: str, external_payment_id: str
    ) -> PaymentAttempt | None:
        statement = self.scoped(
            select(PaymentAttempt).where(
                PaymentAttempt.provider == provider,
                PaymentAttempt.external_payment_id == external_payment_id,
            )
        )
        return self.session.scalar(statement)


class RecoveryActionRepository(TenantRepository[RecoveryAction]):
    def __init__(self, session: Session, merchant_id: str) -> None:
        super().__init__(session, RecoveryAction, merchant_id)

    def by_idempotency_key(self, key: str) -> RecoveryAction | None:
        statement = self.scoped(select(RecoveryAction).where(RecoveryAction.idempotency_key == key))
        return self.session.scalar(statement)


class ScheduledJobRepository(TenantRepository[ScheduledJob]):
    def __init__(self, session: Session, merchant_id: str) -> None:
        super().__init__(session, ScheduledJob, merchant_id)

    def claim_due(
        self,
        now: datetime,
        lease_until: datetime,
    ) -> ScheduledJob | None:
        statement = (
            select(ScheduledJob)
            .where(
                ScheduledJob.merchant_id == self.merchant_id,
                ScheduledJob.status == JobStatus.PENDING,
                ScheduledJob.due_at <= now,
            )
            .order_by(ScheduledJob.due_at, ScheduledJob.created_at)
            .with_for_update(skip_locked=True)
        )
        job = self.session.scalar(statement)
        if job is None:
            return None
        job.status = JobStatus.CLAIMED
        job.lease_until = lease_until
        job.attempt_count += 1
        return job


class UnitOfWork:
    """Explicit transaction boundary shared by application services."""

    def __init__(self, session: Session, merchant_id: str) -> None:
        self.session = session
        self.merchant_id = merchant_id
        self.obligations = ObligationRepository(session, merchant_id)
        self.cases = RecoveryCaseRepository(session, merchant_id)
        self.payment_attempts = PaymentAttemptRepository(session, merchant_id)
        self.actions = RecoveryActionRepository(session, merchant_id)
        self.jobs = ScheduledJobRepository(session, merchant_id)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
