from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.contracts import ActionType
from app.cases.state_machine import ActorType
from app.jobs.service import JobConfig, JobService
from app.persistence.models import (
    AuditEvent,
    Customer,
    PolicyDecision,
    RecoveryCase,
    RecoveryCaseStatus,
)
from app.policy.evaluator import PolicyEvaluationContext, evaluate_policy
from app.policy.schema import Channel
from app.policy.service import PolicyService


class ActionCommandStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    BLOCKED = "BLOCKED"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"


@dataclass(frozen=True)
class ActionCommandResult:
    status: ActionCommandStatus
    case_id: str
    policy_decision_id: str
    job_id: str | None
    reason: str


class ActionCommandService:
    """Owns server-side action requests; provider effects remain worker-owned."""

    _REGISTERED_EFFECTS = frozenset(
        {
            ActionType.GENERATE_PAYMENT_LINK,
            ActionType.SEND_EMAIL,
            ActionType.SEND_SMS,
            ActionType.SEND_WHATSAPP,
        }
    )

    def __init__(self, session: Session, merchant_id: str, job_config: JobConfig) -> None:
        if not merchant_id:
            raise ValueError("merchant_id is required")
        self.session = session
        self.merchant_id = merchant_id
        self.job_config = job_config

    def request(
        self,
        *,
        case_id: str,
        action_type: ActionType,
        idempotency_key: str,
        due_at: datetime,
        actor_id: str,
        channel: Channel | None = None,
        recommendation_id: str | None = None,
        correlation_id: str = "action-command",
    ) -> ActionCommandResult:
        if action_type not in self._REGISTERED_EFFECTS:
            raise ValueError("action type is not a registered executable effect")
        if not idempotency_key or not actor_id:
            raise ValueError("idempotency_key and actor_id are required")
        if due_at.tzinfo is None:
            raise ValueError("due_at must include a timezone")
        self.session.rollback()
        active = PolicyService(self.session, self.merchant_id).active()
        if active is None:
            raise LookupError("active merchant policy not found")
        policy_version, policy = active
        self.session.rollback()
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
            customer_opted_out = False
            if case.customer_id is not None:
                customer = self.session.scalar(
                    select(Customer).where(
                        Customer.id == case.customer_id,
                        Customer.merchant_id == self.merchant_id,
                    )
                )
                customer_opted_out = customer is None or customer.opted_out_at is not None
            expected_channel = channel or {
                ActionType.SEND_EMAIL: Channel.EMAIL,
                ActionType.SEND_SMS: Channel.SMS,
                ActionType.SEND_WHATSAPP: Channel.WHATSAPP,
            }.get(action_type)
            evaluation = evaluate_policy(
                policy,
                PolicyEvaluationContext(
                    action_type=action_type,
                    case_status=RecoveryCaseStatus(case.status),
                    amount_at_risk_minor_units=self._amount(case.obligation_id),
                    customer_opted_out=customer_opted_out,
                    incident_active=case.incident_suppressed,
                    now=datetime.now(UTC),
                    channel=expected_channel,
                ),
            )
            decision = PolicyDecision(
                merchant_id=self.merchant_id,
                recovery_case_id=case.id,
                recommendation_id=recommendation_id,
                policy_version_id=policy_version.id,
                result=evaluation.result,
                decisive_rule=evaluation.decisive_rule,
                reason=evaluation.reason,
                input_snapshot_json={
                    "action_type": action_type.value,
                    "amount_at_risk_minor_units": self._amount(case.obligation_id),
                    "customer_opted_out": customer_opted_out,
                    "incident_active": case.incident_suppressed,
                },
                actor_type=ActorType.OPERATOR,
                correlation_id=correlation_id,
            )
            self.session.add(decision)
            self.session.flush()
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="policy_decision",
                    entity_id=decision.id,
                    event_type="ACTION_REQUEST_EVALUATED",
                    actor_type=ActorType.OPERATOR,
                    actor_id=actor_id,
                    reason=evaluation.reason,
                    metadata_safe_json={"decisive_rule": evaluation.decisive_rule},
                    correlation_id=correlation_id,
                )
            )
            decision_id = decision.id
            policy_version_id = policy_version.id
        if evaluation.result not in {"ALLOW", "SCHEDULE"}:
            result_status = (
                ActionCommandStatus.REQUIRES_APPROVAL
                if evaluation.result == "REQUIRE_APPROVAL"
                else ActionCommandStatus.BLOCKED
            )
            return ActionCommandResult(result_status, case_id, decision_id, None, evaluation.reason)
        self.session.rollback()
        job = JobService(self.session, self.merchant_id, self.job_config).schedule_action(
            case_id=case_id,
            policy_decision_id=decision_id,
            policy_version_id=policy_version_id,
            action_type=action_type.value,
            idempotency_key=idempotency_key,
            due_at=due_at,
            channel=expected_channel.value if expected_channel else None,
            recommendation_id=recommendation_id,
            correlation_id=correlation_id,
        )
        return ActionCommandResult(
            ActionCommandStatus.SCHEDULED,
            case_id,
            decision_id,
            job.id,
            evaluation.reason,
        )

    def _amount(self, obligation_id: str) -> int:
        from app.persistence.models import Obligation

        obligation = self.session.scalar(
            select(Obligation).where(
                Obligation.id == obligation_id,
                Obligation.merchant_id == self.merchant_id,
            )
        )
        if obligation is None:
            raise LookupError("obligation not found")
        return obligation.amount_at_risk
