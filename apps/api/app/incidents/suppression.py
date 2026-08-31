from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cases.state_machine import ActorType, validate_transition
from app.persistence.models import (
    AuditEvent,
    CaseIncident,
    Incident,
    JobStatus,
    PaymentAttempt,
    RecoveryAction,
    RecoveryCase,
    RecoveryCaseStatus,
    ScheduledJob,
)


@dataclass(frozen=True)
class IncidentSuppressionResult:
    incident_id: str
    associated_case_count: int
    suppressed_case_count: int
    cancelled_job_count: int
    preserved_active_job_count: int


@dataclass(frozen=True)
class IncidentReleaseResult:
    incident_id: str
    released_case_count: int


class IncidentSuppressionService:
    """Applies incident suppression without changing financial truth."""

    def __init__(self, session: Session, merchant_id: str) -> None:
        if not merchant_id:
            raise ValueError("merchant_id is required")
        self.session = session
        self.merchant_id = merchant_id

    def suppress(
        self,
        incident_id: str,
        *,
        correlation_id: str = "incident-suppression",
    ) -> IncidentSuppressionResult:
        if not incident_id:
            raise ValueError("incident_id is required")
        transaction = (
            self.session.begin_nested() if self.session.in_transaction() else self.session.begin()
        )
        with transaction:
            incident = self.session.scalar(
                select(Incident)
                .where(
                    Incident.id == incident_id,
                    Incident.merchant_id == self.merchant_id,
                    Incident.status == "OPEN",
                )
                .with_for_update()
            )
            if incident is None:
                raise LookupError("open incident not found")
            cases = self._affected_cases(incident)
            associated = 0
            suppressed = 0
            cancelled_jobs = 0
            preserved_active_jobs = 0
            for case in cases:
                link = self.session.scalar(
                    select(CaseIncident).where(
                        CaseIncident.incident_id == incident.id,
                        CaseIncident.recovery_case_id == case.id,
                    )
                )
                if link is None:
                    self.session.add(
                        CaseIncident(
                            incident_id=incident.id,
                            recovery_case_id=case.id,
                            association_reason="payment-attempt matches incident dimension",
                        )
                    )
                    associated += 1
                if case.status in {
                    RecoveryCaseStatus.RECOVERED,
                    RecoveryCaseStatus.OPTED_OUT,
                    RecoveryCaseStatus.CANCELLED,
                    RecoveryCaseStatus.EXHAUSTED,
                }:
                    continue
                if case.status != RecoveryCaseStatus.SUPPRESSED:
                    validate_transition(
                        RecoveryCaseStatus(case.status), RecoveryCaseStatus.SUPPRESSED
                    )
                    case.status = RecoveryCaseStatus.SUPPRESSED
                    case.incident_suppressed = True
                    suppressed += 1
                    self._audit(
                        case.id,
                        "CASE_SUPPRESSED_INCIDENT",
                        "future recovery outreach suppressed during payment incident",
                        {"incident_id": incident.id},
                        correlation_id,
                    )
                else:
                    case.incident_suppressed = True
                jobs = list(
                    self.session.scalars(
                        select(ScheduledJob).where(
                            ScheduledJob.merchant_id == self.merchant_id,
                            ScheduledJob.recovery_case_id == case.id,
                            ScheduledJob.status.in_({JobStatus.PENDING, JobStatus.CLAIMED}),
                        )
                    )
                )
                for job in jobs:
                    if job.status == JobStatus.CLAIMED:
                        preserved_active_jobs += 1
                        continue
                    job.status = JobStatus.CANCELLED
                    job.lease_until = None
                    action = self.session.scalar(
                        select(RecoveryAction).where(
                            RecoveryAction.id == job.recovery_action_id,
                            RecoveryAction.merchant_id == self.merchant_id,
                        )
                    )
                    if action is not None and action.status == "SCHEDULED":
                        action.status = "CANCELLED"
                        action.cancelled_at = _utc_naive(datetime.now(UTC))
                    cancelled_jobs += 1
                    self._audit(
                        job.id,
                        "JOB_CANCELLED_INCIDENT",
                        "pending recovery job cancelled during payment incident",
                        {"incident_id": incident.id, "case_id": case.id},
                        correlation_id,
                    )
            return IncidentSuppressionResult(
                incident_id=incident.id,
                associated_case_count=associated,
                suppressed_case_count=suppressed,
                cancelled_job_count=cancelled_jobs,
                preserved_active_job_count=preserved_active_jobs,
            )

    def release_after_cooldown(
        self,
        incident_id: str,
        *,
        now: datetime,
        correlation_id: str = "incident-release",
    ) -> IncidentReleaseResult:
        now_naive = _utc_naive(now)
        transaction = (
            self.session.begin_nested() if self.session.in_transaction() else self.session.begin()
        )
        with transaction:
            incident = self.session.scalar(
                select(Incident).where(
                    Incident.id == incident_id,
                    Incident.merchant_id == self.merchant_id,
                )
            )
            if incident is None:
                raise LookupError("incident not found")
            if (
                incident.status != "RESOLVED"
                or incident.cooldown_until is None
                or incident.cooldown_until > now_naive
            ):
                return IncidentReleaseResult(incident.id, 0)
            links = list(
                self.session.scalars(
                    select(CaseIncident).where(CaseIncident.incident_id == incident.id)
                )
            )
            released = 0
            for link in links:
                case = self.session.scalar(
                    select(RecoveryCase).where(
                        RecoveryCase.id == link.recovery_case_id,
                        RecoveryCase.merchant_id == self.merchant_id,
                    )
                )
                if case is None or case.status != RecoveryCaseStatus.SUPPRESSED:
                    continue
                validate_transition(RecoveryCaseStatus.SUPPRESSED, RecoveryCaseStatus.WAITING)
                case.status = RecoveryCaseStatus.WAITING
                case.incident_suppressed = False
                released += 1
                self._audit(
                    case.id,
                    "CASE_RELEASED_AFTER_INCIDENT",
                    "recovery case released after incident cooldown",
                    {"incident_id": incident.id},
                    correlation_id,
                )
            return IncidentReleaseResult(incident.id, released)

    def _affected_cases(self, incident: Incident) -> list[RecoveryCase]:
        field, _, value = incident.dimension_key.partition(":")
        statement = (
            select(RecoveryCase)
            .join(PaymentAttempt, PaymentAttempt.recovery_case_id == RecoveryCase.id)
            .where(
                RecoveryCase.merchant_id == self.merchant_id,
                PaymentAttempt.merchant_id == self.merchant_id,
            )
            .distinct()
        )
        if value != "*":
            column = {
                "payment_method": PaymentAttempt.payment_method,
                "failure_code": PaymentAttempt.failure_code,
                "provider": PaymentAttempt.provider,
            }.get(field)
            if column is None:
                raise ValueError("unsupported incident dimension")
            statement = statement.where(column == value)
        return list(self.session.scalars(statement).all())

    def _audit(
        self,
        entity_id: str,
        event_type: str,
        reason: str,
        metadata: dict[str, object],
        correlation_id: str,
    ) -> None:
        self.session.add(
            AuditEvent(
                merchant_id=self.merchant_id,
                entity_type="incident",
                entity_id=entity_id,
                event_type=event_type,
                actor_type=ActorType.SYSTEM,
                reason=reason,
                metadata_safe_json=metadata,
                correlation_id=correlation_id,
            )
        )


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(UTC).replace(tzinfo=None)
