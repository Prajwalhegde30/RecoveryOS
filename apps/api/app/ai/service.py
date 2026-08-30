from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.contracts import RecommendationEvidence, RecommendationOutput, RecommendationSource
from app.ai.fallback import deterministic_fallback
from app.ai.provider import AIProvider, AIProviderError
from app.persistence.models import AuditEvent, Recommendation, RecoveryCase, RevenueEvent


class RecommendationStaleError(Exception):
    """The case changed while an AI provider call was in flight."""


class AIRecommendationService:
    """Creates advisory recommendations without authorizing or executing actions."""

    def __init__(self, session: Session, merchant_id: str, provider: AIProvider | None) -> None:
        self.session = session
        self.merchant_id = merchant_id
        self.provider = provider

    def recommend(self, case_id: str) -> Recommendation:
        if self.provider is None:
            raise AIProviderError("AI provider is not configured")
        evidence = self._load_evidence(case_id)
        output = self.provider.recommend(evidence)
        if output.confidence_percent < 1 or evidence.evidence_conflict:
            raise ValueError("AI recommendation does not meet evidence safety requirements")
        return self._persist(case_id, evidence, output, RecommendationSource.AI)

    def recommend_with_fallback(
        self, case_id: str, *, minimum_confidence_percent: int
    ) -> Recommendation:
        if not 0 <= minimum_confidence_percent <= 100:
            raise ValueError("minimum_confidence_percent must be between 0 and 100")
        evidence = self._load_evidence(case_id)
        fallback_reason: str | None = None
        if self.provider is None:
            fallback_reason = "AI provider is not configured"
            output = deterministic_fallback(evidence)
        else:
            try:
                output = self.provider.recommend(evidence)
                if evidence.evidence_conflict:
                    fallback_reason = "contradictory evidence"
                elif output.confidence_percent < minimum_confidence_percent:
                    fallback_reason = "AI confidence below configured minimum"
            except AIProviderError as exc:
                output = deterministic_fallback(evidence)
                fallback_reason = type(exc).__name__
            if fallback_reason is not None:
                output = deterministic_fallback(evidence)
        return self._persist(
            case_id,
            evidence,
            output,
            RecommendationSource.DETERMINISTIC_FALLBACK
            if fallback_reason is not None
            else RecommendationSource.AI,
            fallback_reason=fallback_reason,
        )

    def fallback(self, case_id: str) -> Recommendation:
        evidence = self._load_evidence(case_id)
        return self._persist(
            case_id,
            evidence,
            deterministic_fallback(evidence),
            RecommendationSource.DETERMINISTIC_FALLBACK,
            fallback_reason="AI provider is not configured",
        )

    def _persist(
        self,
        case_id: str,
        evidence: RecommendationEvidence,
        output: RecommendationOutput,
        source: RecommendationSource,
        *,
        fallback_reason: str | None = None,
    ) -> Recommendation:
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
                source=source,
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
                    reason="validated recommendation persisted as advisory output",
                    metadata_safe_json={
                        "case_id": case_id,
                        "action": output.action,
                        "source": source,
                        "confidence_percent": output.confidence_percent,
                        "prompt_version": output.prompt_version,
                        "model_version": output.model_version,
                        "scoring_version": evidence.scoring_version,
                    },
                    correlation_id="ai-recommendation",
                )
            )
            if fallback_reason is not None:
                self.session.add(
                    AuditEvent(
                        merchant_id=self.merchant_id,
                        entity_type="recovery_case",
                        entity_id=case_id,
                        event_type="AI_FALLBACK_USED",
                        actor_type="system",
                        reason="deterministic recommendation fallback selected",
                        metadata_safe_json={"reason_category": fallback_reason},
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
                evidence_conflict=False,
                scoring_version=scoring_version,
            )
