from __future__ import annotations

from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cases.state_machine import ActorType, validate_transition
from app.persistence.models import (
    AuditEvent,
    Obligation,
    PolicyDecision,
    PolicyVersion,
    Recommendation,
    RecoveryCase,
    RecoveryCaseStatus,
)
from app.policy.evaluator import PolicyEvaluation, PolicyEvaluationContext, evaluate_policy
from app.policy.schema import policy_from_json


class PolicyDecisionService:
    """Persists policy outcomes and approvals; it never executes provider actions."""

    def __init__(self, session: Session, merchant_id: str) -> None:
        self.session = session
        self.merchant_id = merchant_id

    def evaluate_and_persist(
        self,
        case_id: str,
        policy_version_id: str,
        context: PolicyEvaluationContext,
        *,
        recommendation_id: str | None = None,
        correlation_id: str = "policy-evaluation",
    ) -> PolicyDecision:
        with self.session.begin():
            case = self._case(case_id, for_update=True)
            actual_status = RecoveryCaseStatus(case.status)
            if actual_status != context.case_status:
                raise ValueError("policy context case status is stale")
            obligation = self.session.scalar(
                select(Obligation).where(
                    Obligation.id == case.obligation_id,
                    Obligation.merchant_id == self.merchant_id,
                )
            )
            if obligation is None:
                raise LookupError("case obligation not found")
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
            if version.status != "ACTIVE":
                raise ValueError("policy version is not active")
            # The policy amount is always read from the persisted obligation, not caller input.
            context = replace(
                context,
                amount_at_risk_minor_units=obligation.amount_at_risk,
                case_status=actual_status,
            )
            evaluation = evaluate_policy(policy_from_json(version.policy_json), context)
            decision = self._persist_decision(
                case,
                version,
                evaluation,
                context,
                recommendation_id=recommendation_id,
                actor_type=ActorType.SYSTEM,
                correlation_id=correlation_id,
            )
            if evaluation.result == "REQUIRE_APPROVAL":
                if case.status == RecoveryCaseStatus.ACTION_PENDING:
                    self._transition(
                        case,
                        RecoveryCaseStatus.POLICY_CHECK,
                        "policy evaluation started",
                        correlation_id,
                    )
                self._transition(
                    case, RecoveryCaseStatus.ESCALATED, "approval required", correlation_id
                )
            return decision

    def resolve_approval(
        self,
        case_id: str,
        policy_version_id: str,
        *,
        approved: bool,
        admin_id: str,
        reason: str,
        correlation_id: str = "policy-approval",
    ) -> PolicyDecision:
        if not admin_id or not reason:
            raise ValueError("admin_id and reason are required")
        with self.session.begin():
            case = self._case(case_id, for_update=True)
            version = self.session.scalar(
                select(PolicyVersion).where(
                    PolicyVersion.id == policy_version_id,
                    PolicyVersion.merchant_id == self.merchant_id,
                )
            )
            if version is None:
                raise LookupError("policy version not found")
            latest = self.session.scalar(
                select(PolicyDecision)
                .where(
                    PolicyDecision.merchant_id == self.merchant_id,
                    PolicyDecision.recovery_case_id == case_id,
                    PolicyDecision.policy_version_id == version.id,
                    PolicyDecision.result == "REQUIRE_APPROVAL",
                )
                .order_by(PolicyDecision.created_at.desc())
            )
            if latest is None:
                raise LookupError("pending approval not found")
            result = "ALLOW" if approved else "BLOCK"
            decision = PolicyDecision(
                merchant_id=self.merchant_id,
                recovery_case_id=case_id,
                recommendation_id=latest.recommendation_id,
                policy_version_id=version.id,
                result=result,
                decisive_rule="HUMAN_APPROVAL" if approved else "HUMAN_REJECTION",
                reason=reason,
                input_snapshot_json={"approved": approved, "prior_decision_id": latest.id},
                actor_type=ActorType.ADMIN,
                correlation_id=correlation_id,
            )
            self.session.add(decision)
            self.session.flush()
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="policy_decision",
                    entity_id=decision.id,
                    event_type="POLICY_APPROVAL_RESOLVED",
                    actor_type=ActorType.ADMIN,
                    actor_id=admin_id,
                    reason=reason,
                    metadata_safe_json={"approved": approved, "policy_version": version.version},
                    correlation_id=correlation_id,
                )
            )
            if case.status == RecoveryCaseStatus.ESCALATED:
                self._transition(
                    case,
                    RecoveryCaseStatus.ACTION_PENDING if approved else RecoveryCaseStatus.WAITING,
                    "admin approval resolved",
                    correlation_id,
                )
            return decision

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

    def _persist_decision(
        self,
        case: RecoveryCase,
        version: PolicyVersion,
        evaluation: PolicyEvaluation,
        context: PolicyEvaluationContext,
        *,
        recommendation_id: str | None,
        actor_type: ActorType,
        correlation_id: str,
    ) -> PolicyDecision:
        decision = PolicyDecision(
            merchant_id=self.merchant_id,
            recovery_case_id=case.id,
            recommendation_id=recommendation_id,
            policy_version_id=version.id,
            result=evaluation.result,
            decisive_rule=evaluation.decisive_rule,
            reason=evaluation.reason,
            input_snapshot_json={
                "action_type": context.action_type,
                "case_status": context.case_status,
                "amount_at_risk_minor_units": context.amount_at_risk_minor_units,
                "payment_verified": context.payment_verified,
                "customer_opted_out": context.customer_opted_out,
                "stale_or_invalid": context.stale_or_invalid,
                "incident_active": context.incident_active,
                "case_contact_count": context.case_contact_count,
                "customer_contact_count": context.customer_contact_count,
                "channel": context.channel,
                "fallback_action": evaluation.fallback_action,
            },
            actor_type=actor_type,
            correlation_id=correlation_id,
        )
        self.session.add(decision)
        self.session.flush()
        self.session.add(
            AuditEvent(
                merchant_id=self.merchant_id,
                entity_type="policy_decision",
                entity_id=decision.id,
                event_type="POLICY_DECISION_RECORDED",
                actor_type=actor_type,
                reason=evaluation.reason,
                metadata_safe_json={
                    "case_id": case.id,
                    "result": evaluation.result,
                    "decisive_rule": evaluation.decisive_rule,
                    "policy_version": version.version,
                },
                correlation_id=correlation_id,
            )
        )
        return decision

    def _transition(
        self, case: RecoveryCase, target: RecoveryCaseStatus, reason: str, correlation_id: str
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
                reason=reason,
                metadata_safe_json={},
                correlation_id=correlation_id,
            )
        )
