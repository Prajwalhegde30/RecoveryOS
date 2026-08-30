from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cases.state_machine import ActorType, validate_transition
from app.persistence.models import (
    AuditEvent,
    JobStatus,
    PolicyDecision,
    PolicyVersion,
    Recommendation,
    RecoveryAction,
    RecoveryCase,
    RecoveryCaseStatus,
    ScheduledJob,
)
from app.persistence.repositories import ScheduledJobRepository


@dataclass(frozen=True)
class JobConfig:
    max_attempts: int
    lease_seconds: int
    backoff_base_seconds: int
    backoff_max_seconds: int

    def __post_init__(self) -> None:
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if self.lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if self.backoff_base_seconds <= 0:
            raise ValueError("backoff_base_seconds must be positive")
        if self.backoff_max_seconds < self.backoff_base_seconds:
            raise ValueError("backoff_max_seconds must be at least the base backoff")


class JobService:
    """Owns durable job lifecycle and action reservation, not provider execution."""

    def __init__(self, session: Session, merchant_id: str, config: JobConfig) -> None:
        self.session = session
        self.merchant_id = merchant_id
        self.config = config

    def schedule_action(
        self,
        *,
        case_id: str,
        policy_decision_id: str,
        policy_version_id: str,
        action_type: str,
        idempotency_key: str,
        due_at: datetime,
        job_type: str = "recovery_action",
        channel: str | None = None,
        recommendation_id: str | None = None,
        correlation_id: str = "job-schedule",
    ) -> ScheduledJob:
        if not idempotency_key or not job_type:
            raise ValueError("idempotency_key and job_type are required")
        due_at_naive = _utc_naive(due_at)
        try:
            with self.session.begin():
                case = self._case(case_id, for_update=True)
                decision = self.session.scalar(
                    select(PolicyDecision).where(
                        PolicyDecision.id == policy_decision_id,
                        PolicyDecision.merchant_id == self.merchant_id,
                        PolicyDecision.recovery_case_id == case_id,
                    )
                )
                if decision is None:
                    raise LookupError("policy decision not found")
                if decision.policy_version_id != policy_version_id:
                    raise ValueError("job policy version does not match policy decision")
                if decision.result not in {"ALLOW", "SCHEDULE"}:
                    raise ValueError("only allowed or scheduled policy decisions can create jobs")
                version = self.session.scalar(
                    select(PolicyVersion).where(
                        PolicyVersion.id == policy_version_id,
                        PolicyVersion.merchant_id == self.merchant_id,
                    )
                )
                if version is None:
                    raise LookupError("policy version not found")
                if recommendation_id is not None:
                    recommendation = self.session.scalar(
                        select(Recommendation).where(
                            Recommendation.id == recommendation_id,
                            Recommendation.merchant_id == self.merchant_id,
                            Recommendation.recovery_case_id == case_id,
                        )
                    )
                    if recommendation is None:
                        raise LookupError("recommendation not found")
                action = self.session.scalar(
                    select(RecoveryAction).where(
                        RecoveryAction.merchant_id == self.merchant_id,
                        RecoveryAction.idempotency_key == idempotency_key,
                    )
                )
                if action is None:
                    action = RecoveryAction(
                        merchant_id=self.merchant_id,
                        recovery_case_id=case_id,
                        recommendation_id=recommendation_id,
                        policy_version_id=policy_version_id,
                        action_type=action_type,
                        channel=channel,
                        status="SCHEDULED",
                        idempotency_key=idempotency_key,
                        attempt_number=1,
                        cost_minor_units=0,
                        correlation_id=correlation_id,
                    )
                    self.session.add(action)
                    self.session.flush()
                elif (
                    action.recovery_case_id != case_id
                    or action.policy_version_id != policy_version_id
                ):
                    raise ValueError("action idempotency key belongs to another scope")
                job_key = f"{job_type}:{idempotency_key}"
                job = self.session.scalar(
                    select(ScheduledJob).where(
                        ScheduledJob.merchant_id == self.merchant_id,
                        ScheduledJob.idempotency_key == job_key,
                    )
                )
                if job is not None:
                    return job
                job = ScheduledJob(
                    merchant_id=self.merchant_id,
                    recovery_case_id=case_id,
                    recovery_action_id=action.id,
                    policy_decision_id=policy_decision_id,
                    policy_version_id=policy_version_id,
                    job_type=job_type,
                    status=JobStatus.PENDING,
                    due_at=due_at_naive,
                    attempt_count=0,
                    max_attempts=self.config.max_attempts,
                    idempotency_key=job_key,
                    correlation_id=correlation_id,
                )
                self.session.add(job)
                self.session.flush()
                if case.status == RecoveryCaseStatus.POLICY_CHECK:
                    self._transition(case, RecoveryCaseStatus.SCHEDULED, correlation_id)
                self.session.add(
                    AuditEvent(
                        merchant_id=self.merchant_id,
                        entity_type="scheduled_job",
                        entity_id=job.id,
                        event_type="ACTION_SCHEDULED",
                        actor_type=ActorType.SYSTEM,
                        reason="approved recovery action scheduled durably",
                        metadata_safe_json={
                            "case_id": case_id,
                            "action_id": action.id,
                            "policy_decision_id": policy_decision_id,
                            "policy_version_id": policy_version_id,
                        },
                        correlation_id=correlation_id,
                    )
                )
                return job
        except IntegrityError:
            self.session.rollback()
            existing = self.session.scalar(
                select(ScheduledJob).where(
                    ScheduledJob.merchant_id == self.merchant_id,
                    ScheduledJob.idempotency_key == f"{job_type}:{idempotency_key}",
                )
            )
            if existing is None:
                raise
            return existing

    def claim_due(self, *, now: datetime, correlation_id: str = "job-claim") -> ScheduledJob | None:
        now_naive = _utc_naive(now)
        lease_until = now_naive + timedelta(seconds=self.config.lease_seconds)
        with self.session.begin():
            job = ScheduledJobRepository(self.session, self.merchant_id).claim_due(
                now_naive, lease_until
            )
            if job is not None:
                self.session.add(
                    AuditEvent(
                        merchant_id=self.merchant_id,
                        entity_type="scheduled_job",
                        entity_id=job.id,
                        event_type="JOB_CLAIMED",
                        actor_type=ActorType.WORKER,
                        reason="worker claimed due job with lease",
                        metadata_safe_json={"attempt_count": job.attempt_count},
                        correlation_id=correlation_id,
                    )
                )
            return job

    def cancel(
        self, job_id: str, *, reason: str, correlation_id: str = "job-cancel"
    ) -> ScheduledJob:
        if not reason:
            raise ValueError("reason is required")
        with self.session.begin():
            job = self._job(job_id, for_update=True)
            if job.status in {JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.FAILED}:
                return job
            job.status = JobStatus.CANCELLED
            job.lease_until = None
            action = self._action(job.recovery_action_id)
            if action is not None:
                action.status = "CANCELLED"
                action.cancelled_at = _utc_naive(datetime.now(UTC))
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="scheduled_job",
                    entity_id=job.id,
                    event_type="JOB_CANCELLED",
                    actor_type=ActorType.SYSTEM,
                    reason=reason,
                    metadata_safe_json={},
                    correlation_id=correlation_id,
                )
            )
            return job

    def retry_or_fail(
        self,
        job_id: str,
        *,
        now: datetime,
        error_category: str,
        error_safe: str,
        correlation_id: str = "job-retry",
    ) -> ScheduledJob:
        if not error_category or not error_safe:
            raise ValueError("error_category and error_safe are required")
        now_naive = _utc_naive(now)
        with self.session.begin():
            job = self._job(job_id, for_update=True)
            if job.status not in {JobStatus.CLAIMED, JobStatus.PENDING}:
                return job
            job.last_error_category = error_category
            job.last_error_safe = error_safe[:512]
            job.lease_until = None
            action = self._action(job.recovery_action_id)
            if job.attempt_count >= job.max_attempts:
                job.status = JobStatus.FAILED
                if action is not None:
                    action.status = "FAILED"
                    action.failure_category = error_category
                    action.failure_detail_safe = error_safe[:512]
                event_type = "JOB_FAILED_TERMINAL"
            else:
                delay = min(
                    self.config.backoff_base_seconds * 2 ** max(job.attempt_count - 1, 0),
                    self.config.backoff_max_seconds,
                )
                job.status = JobStatus.PENDING
                job.next_retry_at = now_naive + timedelta(seconds=delay)
                job.due_at = job.next_retry_at
                if action is not None:
                    action.status = "SCHEDULED"
                    action.failure_category = error_category
                    action.failure_detail_safe = error_safe[:512]
                event_type = "JOB_RETRY_SCHEDULED"
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="scheduled_job",
                    entity_id=job.id,
                    event_type=event_type,
                    actor_type=ActorType.WORKER,
                    reason=error_safe[:512],
                    metadata_safe_json={"error_category": error_category},
                    correlation_id=correlation_id,
                )
            )
            return job

    def recover_expired_leases(self, *, now: datetime, correlation_id: str = "job-recovery") -> int:
        now_naive = _utc_naive(now)
        with self.session.begin():
            jobs = list(
                self.session.scalars(
                    select(ScheduledJob)
                    .where(
                        ScheduledJob.merchant_id == self.merchant_id,
                        ScheduledJob.status == JobStatus.CLAIMED,
                        ScheduledJob.lease_until.is_not(None),
                        ScheduledJob.lease_until <= now_naive,
                    )
                    .with_for_update()
                ).all()
            )
            for job in jobs:
                job.status = JobStatus.PENDING
                job.lease_until = None
                job.due_at = now_naive
                self.session.add(
                    AuditEvent(
                        merchant_id=self.merchant_id,
                        entity_type="scheduled_job",
                        entity_id=job.id,
                        event_type="JOB_LEASE_RECOVERED",
                        actor_type=ActorType.WORKER,
                        reason="expired worker lease returned job to pending",
                        metadata_safe_json={},
                        correlation_id=correlation_id,
                    )
                )
            return len(jobs)

    def complete(self, job_id: str, *, correlation_id: str = "job-complete") -> ScheduledJob:
        with self.session.begin():
            job = self._job(job_id, for_update=True)
            if job.status == JobStatus.COMPLETED:
                return job
            if job.status != JobStatus.CLAIMED:
                raise ValueError("only a claimed job can be completed")
            job.status = JobStatus.COMPLETED
            job.lease_until = None
            action = self._action(job.recovery_action_id)
            if action is not None:
                action.status = "SUCCEEDED"
                action.executed_at = _utc_naive(datetime.now(UTC))
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="scheduled_job",
                    entity_id=job.id,
                    event_type="JOB_COMPLETED",
                    actor_type=ActorType.WORKER,
                    reason="job effect completed by worker",
                    metadata_safe_json={},
                    correlation_id=correlation_id,
                )
            )
            return job

    def _case(self, case_id: str, *, for_update: bool) -> RecoveryCase:
        statement = select(RecoveryCase).where(
            RecoveryCase.id == case_id,
            RecoveryCase.merchant_id == self.merchant_id,
        )
        if for_update:
            statement = statement.with_for_update()
        case = self.session.scalar(statement)
        if case is None:
            raise LookupError("recovery case not found")
        return case

    def _job(self, job_id: str, *, for_update: bool) -> ScheduledJob:
        statement = select(ScheduledJob).where(
            ScheduledJob.id == job_id,
            ScheduledJob.merchant_id == self.merchant_id,
        )
        if for_update:
            statement = statement.with_for_update()
        job = self.session.scalar(statement)
        if job is None:
            raise LookupError("scheduled job not found")
        return job

    def _action(self, action_id: str | None) -> RecoveryAction | None:
        if action_id is None:
            return None
        return self.session.scalar(
            select(RecoveryAction).where(
                RecoveryAction.id == action_id,
                RecoveryAction.merchant_id == self.merchant_id,
            )
        )

    def _transition(
        self, case: RecoveryCase, target: RecoveryCaseStatus, correlation_id: str
    ) -> None:
        current = RecoveryCaseStatus(case.status)
        validate_transition(current, target)
        case.status = target
        self.session.add(
            AuditEvent(
                merchant_id=self.merchant_id,
                entity_type="recovery_case",
                entity_id=case.id,
                event_type="CASE_STATE_CHANGED",
                actor_type=ActorType.SYSTEM,
                from_state=current,
                to_state=target,
                reason="durable action scheduled",
                metadata_safe_json={},
                correlation_id=correlation_id,
            )
        )


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(UTC).replace(tzinfo=None)
