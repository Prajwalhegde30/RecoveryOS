from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.persistence.models import (
    AttributionRecord,
    AuditEvent,
    Incident,
    PaymentAttempt,
    PolicyDecision,
    Recommendation,
    RecoveryAction,
    RecoveryCase,
    RevenueEvent,
    ScheduledJob,
)


class OperationalMetricsService:
    """Derives tenant-scoped operational counters from durable domain records."""

    def __init__(self, session: Session, merchant_id: str) -> None:
        if not merchant_id:
            raise ValueError("merchant_id is required")
        self.session = session
        self.merchant_id = merchant_id

    def calculate(self) -> dict[str, int]:
        return {
            "events_received": self._count(RevenueEvent),
            "events_processed": self._count(
                RevenueEvent, RevenueEvent.processing_status == "PROCESSED"
            ),
            "events_duplicate": self._count(
                AuditEvent, AuditEvent.event_type == "EVENT_DUPLICATE_RECEIVED"
            ),
            "cases_total": self._count(RecoveryCase),
            "cases_open": self._count(RecoveryCase, RecoveryCase.closed_at.is_(None)),
            "recommendations_total": self._count(Recommendation),
            "recommendations_fallback": self._count(
                Recommendation, Recommendation.source == "DETERMINISTIC_FALLBACK"
            ),
            "policy_decisions_total": self._count(PolicyDecision),
            "policy_decisions_blocked": self._count(
                PolicyDecision, PolicyDecision.result == "BLOCK"
            ),
            "policy_decisions_approval": self._count(
                PolicyDecision, PolicyDecision.result == "REQUIRE_APPROVAL"
            ),
            "jobs_pending": self._count(ScheduledJob, ScheduledJob.status == "PENDING"),
            "jobs_claimed": self._count(ScheduledJob, ScheduledJob.status == "CLAIMED"),
            "jobs_completed": self._count(ScheduledJob, ScheduledJob.status == "COMPLETED"),
            "jobs_failed": self._count(ScheduledJob, ScheduledJob.status == "FAILED"),
            "actions_succeeded": self._count(RecoveryAction, RecoveryAction.status == "SUCCEEDED"),
            "actions_failed": self._count(RecoveryAction, RecoveryAction.status == "FAILED"),
            "provider_failures": self._count(
                RecoveryAction,
                RecoveryAction.failure_category.in_(
                    {
                        "payment_timeout",
                        "payment_transport_error",
                        "payment_rate_limited",
                        "payment_invalid_response",
                        "payment_ambiguous_result",
                        "messaging_timeout",
                        "messaging_transport_error",
                        "messaging_rate_limited",
                        "messaging_invalid_response",
                        "messaging_ambiguous_result",
                    }
                ),
            ),
            "payment_attempts_failed": self._count(
                PaymentAttempt, PaymentAttempt.status == "failed"
            ),
            "actions_cancelled": self._count(RecoveryAction, RecoveryAction.status == "CANCELLED"),
            "incidents_open": self._count(Incident, Incident.status == "OPEN"),
            "attributions_natural": self._count(
                AttributionRecord, AttributionRecord.outcome == "NATURAL_RECOVERY"
            ),
            "attributions_assisted": self._count(
                AttributionRecord, AttributionRecord.outcome == "ASSISTED_RECOVERY"
            ),
            "attributions_suppressed": self._count(
                AttributionRecord, AttributionRecord.outcome == "SUPPRESSED"
            ),
            "attributions_unrecovered": self._count(
                AttributionRecord, AttributionRecord.outcome == "UNRECOVERED"
            ),
        }

    def _count(self, model: Any, condition: Any | None = None) -> int:
        statement = (
            select(func.count())
            .select_from(model)
            .where(model.merchant_id == self.merchant_id)
        )
        if condition is not None:
            statement = statement.where(condition)
        return int(self.session.scalar(statement) or 0)
