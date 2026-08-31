from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cases.state_machine import ActorType
from app.persistence.models import AuditEvent, Incident, PaymentAttempt


class IncidentDetectionStatus(StrEnum):
    NO_INCIDENT = "NO_INCIDENT"
    OPENED = "OPENED"
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    COOLDOWN = "COOLDOWN"


@dataclass(frozen=True)
class IncidentDetectorConfig:
    """Validated detector inputs; business thresholds are never hidden constants."""

    baseline_window: timedelta
    current_window: timedelta
    minimum_baseline_attempts: int
    minimum_current_attempts: int
    degradation_threshold_percentage_points: int
    resolution_threshold_percentage_points: int
    cooldown: timedelta
    dimension_field: str = "payment_method"
    detector_version: str = "incident-detector-v1"

    def __post_init__(self) -> None:
        if self.baseline_window <= timedelta(0) or self.current_window <= timedelta(0):
            raise ValueError("incident windows must be positive")
        if self.minimum_baseline_attempts <= 0 or self.minimum_current_attempts <= 0:
            raise ValueError("incident minimum samples must be positive")
        if not 0 <= self.degradation_threshold_percentage_points <= 100:
            raise ValueError("degradation threshold must be between 0 and 100")
        if not 0 <= self.resolution_threshold_percentage_points <= 100:
            raise ValueError("resolution threshold must be between 0 and 100")
        if self.cooldown < timedelta(0):
            raise ValueError("incident cooldown must not be negative")
        if self.dimension_field not in {"payment_method", "failure_code", "provider"}:
            raise ValueError("unsupported incident dimension field")
        if not self.detector_version:
            raise ValueError("detector_version is required")


@dataclass(frozen=True)
class IncidentDetectionResult:
    status: IncidentDetectionStatus
    incident_id: str | None
    dimension_key: str
    baseline_attempt_count: int
    baseline_failure_count: int
    baseline_failure_rate_percent: int
    current_attempt_count: int
    current_failure_count: int
    current_failure_rate_percent: int
    reason: str


@dataclass(frozen=True)
class _WindowStats:
    start: datetime
    end: datetime
    attempt_count: int
    failure_count: int
    failed_amount_minor_units: int

    @property
    def failure_rate_percent(self) -> int:
        if self.attempt_count == 0:
            return 0
        return self.failure_count * 100 // self.attempt_count

    def as_json(self) -> dict[str, object]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "attempt_count": self.attempt_count,
            "failure_count": self.failure_count,
            "failure_rate_percent": self.failure_rate_percent,
            "failed_amount_minor_units": self.failed_amount_minor_units,
        }


class IncidentDetectorService:
    """Detects correlated payment degradation without creating financial state."""

    def __init__(self, session: Session, merchant_id: str, config: IncidentDetectorConfig) -> None:
        if not merchant_id:
            raise ValueError("merchant_id is required")
        self.session = session
        self.merchant_id = merchant_id
        self.config = config

    def detect(
        self,
        *,
        now: datetime,
        dimension_value: str | None = None,
        correlation_id: str = "incident-detector",
    ) -> IncidentDetectionResult:
        now_utc = _utc_naive(now)
        dimension_key = self._dimension_key(dimension_value)
        baseline_end = now_utc - self.config.current_window
        baseline_start = baseline_end - self.config.baseline_window
        current_start = baseline_end
        transaction = (
            self.session.begin_nested() if self.session.in_transaction() else self.session.begin()
        )
        with transaction:
            baseline = self._stats(baseline_start, baseline_end, dimension_value)
            current = self._stats(current_start, now_utc, dimension_value)
            active = self.session.scalar(
                select(Incident)
                .where(
                    Incident.merchant_id == self.merchant_id,
                    Incident.dimension_key == dimension_key,
                    Incident.status == "OPEN",
                )
                .order_by(Incident.opened_at.desc())
                .with_for_update()
            )
            cooldown = self.session.scalar(
                select(Incident)
                .where(
                    Incident.merchant_id == self.merchant_id,
                    Incident.dimension_key == dimension_key,
                    Incident.status == "RESOLVED",
                    Incident.cooldown_until.is_not(None),
                    Incident.cooldown_until > now_utc,
                )
                .order_by(Incident.resolved_at.desc())
                .with_for_update()
            )
            result = self._evaluate(
                baseline,
                current,
                active=active,
                cooldown=cooldown,
                dimension_key=dimension_key,
                now=now_utc,
                correlation_id=correlation_id,
            )
            return result

    def _evaluate(
        self,
        baseline: _WindowStats,
        current: _WindowStats,
        *,
        active: Incident | None,
        cooldown: Incident | None,
        dimension_key: str,
        now: datetime,
        correlation_id: str,
    ) -> IncidentDetectionResult:
        enough_baseline = baseline.attempt_count >= self.config.minimum_baseline_attempts
        enough_current = current.attempt_count >= self.config.minimum_current_attempts
        degraded = (
            enough_baseline
            and enough_current
            and current.failure_rate_percent
            >= baseline.failure_rate_percent + self.config.degradation_threshold_percentage_points
        )
        recovered = (
            enough_current
            and current.failure_rate_percent
            <= baseline.failure_rate_percent + self.config.resolution_threshold_percentage_points
        )
        if active is not None:
            if recovered:
                active.status = "RESOLVED"
                active.resolved_at = now
                active.cooldown_until = now + self.config.cooldown
                active.current_window = current.as_json()
                self._audit(
                    entity_id=active.id,
                    event_type="INCIDENT_RESOLVED",
                    reason="current payment failure rate returned within resolution range",
                    metadata={"dimension_key": dimension_key, "current": current.as_json()},
                    correlation_id=correlation_id,
                )
                return self._result(
                    IncidentDetectionStatus.RESOLVED,
                    active,
                    dimension_key,
                    baseline,
                    current,
                    "incident resolved and cooldown started",
                )
            active.baseline_window = baseline.as_json()
            active.current_window = current.as_json()
            active.evidence_json = self._evidence(baseline, current, dimension_key)
            active.confidence = self._confidence(baseline, current)
            self._audit(
                entity_id=active.id,
                event_type="INCIDENT_UPDATED",
                reason="active incident evidence refreshed",
                metadata={"dimension_key": dimension_key, "current": current.as_json()},
                correlation_id=correlation_id,
            )
            return self._result(
                IncidentDetectionStatus.ACTIVE,
                active,
                dimension_key,
                baseline,
                current,
                "active incident remains open",
            )
        if cooldown is not None:
            return self._result(
                IncidentDetectionStatus.COOLDOWN,
                cooldown,
                dimension_key,
                baseline,
                current,
                "incident cooldown prevents immediate reopening",
            )
        if not degraded:
            return self._result(
                IncidentDetectionStatus.NO_INCIDENT,
                None,
                dimension_key,
                baseline,
                current,
                "configured sample and degradation conditions were not met",
            )
        incident = Incident(
            merchant_id=self.merchant_id,
            dimension_key=dimension_key,
            status="OPEN",
            baseline_window=baseline.as_json(),
            current_window=current.as_json(),
            confidence=self._confidence(baseline, current),
            evidence_json=self._evidence(baseline, current, dimension_key),
            detector_version=self.config.detector_version,
        )
        self.session.add(incident)
        self.session.flush()
        self._audit(
            entity_id=incident.id,
            event_type="INCIDENT_OPENED",
            reason="current payment failure rate exceeds configured degradation range",
            metadata={"dimension_key": dimension_key, "current": current.as_json()},
            correlation_id=correlation_id,
        )
        return self._result(
            IncidentDetectionStatus.OPENED,
            incident,
            dimension_key,
            baseline,
            current,
            "systemic payment degradation detected",
        )

    def _stats(self, start: datetime, end: datetime, dimension_value: str | None) -> _WindowStats:
        statement = select(PaymentAttempt).where(
            PaymentAttempt.merchant_id == self.merchant_id,
            PaymentAttempt.provider_event_at >= start,
            PaymentAttempt.provider_event_at < end,
        )
        if dimension_value is not None:
            statement = statement.where(self._dimension_column() == dimension_value)
        attempts = list(self.session.scalars(statement).all())
        failed = [attempt for attempt in attempts if attempt.status == "failed"]
        return _WindowStats(
            start=start,
            end=end,
            attempt_count=len(attempts),
            failure_count=len(failed),
            failed_amount_minor_units=sum(attempt.amount for attempt in failed),
        )

    def _dimension_column(self):
        return {
            "payment_method": PaymentAttempt.payment_method,
            "failure_code": PaymentAttempt.failure_code,
            "provider": PaymentAttempt.provider,
        }[self.config.dimension_field]

    def _dimension_key(self, dimension_value: str | None) -> str:
        return f"{self.config.dimension_field}:{dimension_value or '*'}"

    def _confidence(self, baseline: _WindowStats, current: _WindowStats) -> int:
        return min(100, max(0, current.failure_rate_percent - baseline.failure_rate_percent))

    def _evidence(
        self, baseline: _WindowStats, current: _WindowStats, dimension_key: str
    ) -> dict[str, object]:
        return {
            "dimension_key": dimension_key,
            "baseline": baseline.as_json(),
            "current": current.as_json(),
            "detector_version": self.config.detector_version,
        }

    def _result(
        self,
        status: IncidentDetectionStatus,
        incident: Incident | None,
        dimension_key: str,
        baseline: _WindowStats,
        current: _WindowStats,
        reason: str,
    ) -> IncidentDetectionResult:
        return IncidentDetectionResult(
            status=status,
            incident_id=incident.id if incident is not None else None,
            dimension_key=dimension_key,
            baseline_attempt_count=baseline.attempt_count,
            baseline_failure_count=baseline.failure_count,
            baseline_failure_rate_percent=baseline.failure_rate_percent,
            current_attempt_count=current.attempt_count,
            current_failure_count=current.failure_count,
            current_failure_rate_percent=current.failure_rate_percent,
            reason=reason,
        )

    def _audit(
        self,
        *,
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
