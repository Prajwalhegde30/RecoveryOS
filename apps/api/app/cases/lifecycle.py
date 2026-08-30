from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cases.state_machine import ActorType, validate_transition
from app.persistence.models import AuditEvent, RecoveryCase, RecoveryCaseStatus


class CaseLifecycleService:
    def __init__(self, session: Session, merchant_id: str) -> None:
        self.session = session
        self.merchant_id = merchant_id

    def transition(
        self,
        case_id: str,
        target: RecoveryCaseStatus,
        *,
        actor_type: ActorType,
        reason: str,
        correlation_id: str,
    ) -> RecoveryCase:
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
            current = RecoveryCaseStatus(case.status)
            validate_transition(current, target)
            case.status = target
            if target in {
                RecoveryCaseStatus.RECOVERED,
                RecoveryCaseStatus.OPTED_OUT,
                RecoveryCaseStatus.CANCELLED,
                RecoveryCaseStatus.EXHAUSTED,
            }:
                case.closed_at = datetime.now(UTC).replace(tzinfo=None)
            self.session.add(
                AuditEvent(
                    merchant_id=self.merchant_id,
                    entity_type="recovery_case",
                    entity_id=case.id,
                    event_type="CASE_STATE_CHANGED",
                    actor_type=actor_type,
                    from_state=current,
                    to_state=target,
                    reason=reason,
                    metadata_safe_json={},
                    correlation_id=correlation_id,
                )
            )
            return case

    def history(self, case_id: str) -> list[AuditEvent]:
        statement = (
            select(AuditEvent)
            .where(
                AuditEvent.merchant_id == self.merchant_id,
                AuditEvent.entity_type == "recovery_case",
                AuditEvent.entity_id == case_id,
            )
            .order_by(AuditEvent.created_at, AuditEvent.id)
        )
        return list(self.session.scalars(statement).all())
