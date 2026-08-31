from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models import AttributionRecord, Obligation, RecoveryAction, RecoveryCase


@dataclass(frozen=True)
class RecoveryMetrics:
    revenue_at_risk_minor_units: int
    expected_recoverable_minor_units: int
    recovered_minor_units: int
    natural_recovered_minor_units: int
    assisted_recovered_minor_units: int
    suppressed_minor_units: int
    unrecovered_minor_units: int
    recovery_cost_minor_units: int
    net_recovery_minor_units: int
    recovered_case_count: int
    recovery_rate_percent: int
    median_time_to_recovery_seconds: int | None


class RecoveryMetricsService:
    """Reads dashboard metrics from persisted cases, obligations, actions, and attribution."""

    def __init__(self, session: Session, merchant_id: str) -> None:
        if not merchant_id:
            raise ValueError("merchant_id is required")
        self.session = session
        self.merchant_id = merchant_id

    def calculate(self) -> RecoveryMetrics:
        cases = list(
            self.session.scalars(
                select(RecoveryCase).where(RecoveryCase.merchant_id == self.merchant_id)
            )
        )
        obligations = list(
            self.session.scalars(
                select(Obligation).where(Obligation.merchant_id == self.merchant_id)
            )
        )
        at_risk = sum(obligation.amount_at_risk for obligation in obligations)
        expected = sum((case.expected_recoverable_amount or 0) for case in cases)
        recovered = sum(case.recovered_amount for case in cases)
        records = list(
            self.session.scalars(
                select(AttributionRecord).where(AttributionRecord.merchant_id == self.merchant_id)
            )
        )
        natural = sum(
            record.recovered_amount for record in records if record.outcome == "NATURAL_RECOVERY"
        )
        assisted = sum(
            record.recovered_amount for record in records if record.outcome == "ASSISTED_RECOVERY"
        )
        suppressed = sum(
            obligation.amount_at_risk
            for case in cases
            if case.attribution_status == "SUPPRESSED"
            for obligation in obligations
            if obligation.id == case.obligation_id
        )
        unrecovered = sum(
            obligation.amount_at_risk
            for case in cases
            if case.attribution_status == "UNRECOVERED"
            for obligation in obligations
            if obligation.id == case.obligation_id
        )
        costs = sum(
            action.cost_minor_units
            for action in self.session.scalars(
                select(RecoveryAction).where(
                    RecoveryAction.merchant_id == self.merchant_id,
                    RecoveryAction.status == "SUCCEEDED",
                )
            )
        )
        recovered_times = [
            (case.closed_at - case.opened_at).total_seconds()
            for case in cases
            if case.closed_at is not None and case.recovered_amount > 0
        ]
        recovery_rate = recovered * 100 // at_risk if at_risk else 0
        return RecoveryMetrics(
            revenue_at_risk_minor_units=at_risk,
            expected_recoverable_minor_units=expected,
            recovered_minor_units=recovered,
            natural_recovered_minor_units=natural,
            assisted_recovered_minor_units=assisted,
            suppressed_minor_units=suppressed,
            unrecovered_minor_units=unrecovered,
            recovery_cost_minor_units=costs,
            net_recovery_minor_units=recovered - costs,
            recovered_case_count=sum(case.recovered_amount > 0 for case in cases),
            recovery_rate_percent=recovery_rate,
            median_time_to_recovery_seconds=(
                int(median(recovered_times)) if recovered_times else None
            ),
        )
