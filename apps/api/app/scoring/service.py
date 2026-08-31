from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models import (
    AuditEvent,
    Obligation,
    RecoveryCase,
    RecoveryCaseStatus,
    RevenueEvent,
)
from app.scoring.diagnosis import classify
from app.scoring.economics import ScoreResult, ScoringConfig, calculate_score


class CaseAnalysisService:
    def __init__(self, session: Session, merchant_id: str, config: ScoringConfig) -> None:
        self.session = session
        self.merchant_id = merchant_id
        self.config = config

    def analyze(self, case_id: str, *, incident_active: bool = False) -> ScoreResult:
        with self.session.begin():
            case = self.session.scalar(
                select(RecoveryCase)
                .where(
                    RecoveryCase.id == case_id,
                    RecoveryCase.merchant_id == self.merchant_id,
                )
                .with_for_update()
            )
            if case is None:
                raise LookupError("recovery case not found")
            event = self.session.scalar(
                select(RevenueEvent)
                .where(
                    RevenueEvent.merchant_id == self.merchant_id,
                    RevenueEvent.recovery_case_id == case_id,
                )
                .order_by(RevenueEvent.received_at)
            )
            if event is None:
                raise LookupError("case has no normalized revenue event")
            diagnosis = classify(
                event.event_type,
                event.normalized_payload.get("failure_code"),
                incident_active=incident_active,
            )
            result = calculate_score(
                amount_minor_units=self._amount(case),
                diagnosis_category=diagnosis.category,
                diagnosis_confidence_percent=diagnosis.confidence_percent,
                incident_active=incident_active,
                config=self.config,
            )
            current = RecoveryCaseStatus(case.status)
            if current == RecoveryCaseStatus.DETECTED:
                case.status = RecoveryCaseStatus.ANALYZING
                self._audit(case, "ANALYSIS_STARTED", "deterministic analysis started", case.status)
                case.status = RecoveryCaseStatus.ACTION_PENDING
                self._audit(
                    case, "RECOMMENDATION_READY", "deterministic score is ready", case.status
                )
            case.root_cause = diagnosis.category
            case.root_cause_confidence = diagnosis.confidence_percent
            case.recovery_probability = result.probability_percent
            case.probability_version = result.version
            case.expected_recoverable_amount = result.expected_recoverable_amount
            case.priority_score = result.priority_score
            case.priority_version = result.version
            return result

    def _amount(self, case: RecoveryCase) -> int:
        amount = self.session.scalar(
            select(Obligation.amount_at_risk).where(
                Obligation.id == case.obligation_id,
                Obligation.merchant_id == self.merchant_id,
            )
        )
        if amount is None:
            raise LookupError("obligation is outside merchant scope")
        return amount

    def _audit(
        self,
        case: RecoveryCase,
        event_type: str,
        reason: str,
        state: RecoveryCaseStatus,
    ) -> None:
        self.session.add(
            AuditEvent(
                merchant_id=self.merchant_id,
                entity_type="recovery_case",
                entity_id=case.id,
                event_type=event_type,
                actor_type="system",
                to_state=state,
                reason=reason,
                metadata_safe_json={},
                correlation_id="analysis",
            )
        )
