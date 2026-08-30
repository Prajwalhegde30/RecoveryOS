from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.contracts import RecommendationEvidence, RecommendationSource
from app.ai.provider import AIProvider
from app.persistence.models import AuditEvent, Recommendation, RecoveryCase, RevenueEvent


class RecommendationStaleError(Exception):
    """The case changed while an AI provider call was in flight."""


class AIRecommendationService:
    """Creates advisory recommendations without authorizing or executing actions."""

    def __init__(self, session: Session, merchant_id: str, provider: AIProvider) -> None:
        self.session = session
        self.merchant_id = merchant_id
        self.provider = provider

    def recommend(self, case_id: str) -> Recommendation:
        evidence = self._load_evidence(case_id)
        output = self.provider.recommend(evidence)
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
            if case.probability_version != evidence.scoring_version:
                raise RecommendationStaleError("case scoring changed during recommendation")
            recommendation = Recommendation(
                merchant_id=self.merchant_id,
                recovery_case_id=case_id,
                source=RecommendationSource.AI,
                action_type=output.action,
                parameters_json=output.parameters,
                reason_code=output.reason_code,
                rationale=output.rationale,
                evidence_json={"items": output.evidence},
                confidence=output.confidence_percent,
                prompt_version=output.prompt_version,
                model_version=output.model_version,
                scoring_version=evidence.scoring_version,
            )
            self.session.add(recommendation)
            self.session.flush()
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="recommendation",
                    entity_id=recommendation.id,
                    event_type="RECOMMENDATION_CREATED",
                    actor_type="system",
                    reason="validated AI recommendation persisted as advisory output",
                    metadata_safe_json={
                        "case_id": case_id,
                        "action": output.action,
                        "confidence_percent": output.confidence_percent,
                        "prompt_version": output.prompt_version,
                        "model_version": output.model_version,
                        "scoring_version": evidence.scoring_version,
                    },
                    correlation_id="ai-recommendation",
                )
            )
            return recommendation

    def _load_evidence(self, case_id: str) -> RecommendationEvidence:
        with self.session.begin():
            case = self.session.scalar(
                select(RecoveryCase).where(
                    RecoveryCase.id == case_id,
                    RecoveryCase.merchant_id == self.merchant_id,
                )
            )
            if case is None:
                raise LookupError("recovery case not found")
            if case.root_cause is None or case.recovery_probability is None:
                raise LookupError("recovery case has no deterministic analysis")
            scoring_version = case.probability_version or case.priority_version
            if scoring_version is None:
                raise LookupError("recovery case has no scoring version")
            event = self.session.scalar(
                select(RevenueEvent)
                .where(
                    RevenueEvent.merchant_id == self.merchant_id,
                    RevenueEvent.recovery_case_id == case_id,
                )
                .order_by(RevenueEvent.received_at)
            )
            if event is None:
                raise LookupError("recovery case has no normalized revenue event")
            payload = event.normalized_payload
            return RecommendationEvidence(
                source_type=case.source_type,
                root_cause=case.root_cause,
                root_cause_confidence_percent=case.root_cause_confidence or 0,
                recovery_probability_percent=case.recovery_probability,
                expected_recoverable_amount_minor_units=case.expected_recoverable_amount or 0,
                priority_score=case.priority_score or 0,
                payment_method=payload.get("payment_method"),
                failure_code=payload.get("failure_code"),
                attempt_count=case.attempt_count,
                incident_active=case.incident_suppressed,
                scoring_version=scoring_version,
            )
