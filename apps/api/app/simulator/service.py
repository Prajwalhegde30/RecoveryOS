from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.actions.service import ActionCommandService, ActionCommandStatus
from app.ai.contracts import ActionType
from app.ai.service import AIRecommendationService
from app.attribution.service import AttributionConfig, AttributionService
from app.cases.identity import RECOVERABLE_EVENT_TYPES
from app.cases.service import RecoveryCaseService
from app.cases.state_machine import is_open
from app.config import get_settings
from app.customers.service import CustomerOptOutService
from app.events.contracts import EventIngestionResult, RevenueEvent, RevenueEventType
from app.events.service import EventIngestionService
from app.integrations.contracts import PaymentStatus
from app.integrations.executor import ProviderActionExecutor
from app.integrations.simulated import SimulatedMessagingProvider, SimulatedPaymentProvider
from app.jobs.service import JobConfig, JobService
from app.persistence.models import (
    AttributionRecord,
    Merchant,
    PaymentAttempt,
    Recommendation,
    RecoveryCase,
    RecoveryCaseStatus,
)
from app.persistence.models import (
    RevenueEvent as RevenueEventRecord,
)
from app.policy.service import PolicyService
from app.reconciliation.service import PaymentReconciliationService
from app.scoring.economics import ScoringConfig
from app.scoring.service import CaseAnalysisService
from app.workers.service import ProviderPreflightChecker, WorkerService


@dataclass(frozen=True)
class SimulatorConfig:
    """Explicit scenario inputs; no demo result is stored as a fixed total."""

    seed: int
    merchant_ids: tuple[str, ...]
    transaction_count: int
    amounts_minor_units: tuple[int, ...]
    payment_methods: tuple[str, ...]
    failure_codes: tuple[str, ...]
    event_types: tuple[RevenueEventType, ...] = ()
    standard_currency: str = "INR"
    high_value_indices: frozenset[int] = frozenset()
    high_value_amount_minor_units: int | None = None
    duplicate_event_indices: frozenset[int] = frozenset()
    opt_out_indices: frozenset[int] = frozenset()
    incident_indices: frozenset[int] = frozenset()
    natural_recovery_indices: frozenset[int] = frozenset()
    assisted_recovery_indices: frozenset[int] = frozenset()
    provider_failure_indices: frozenset[int] = frozenset()
    scoring_config: ScoringConfig = field(
        default_factory=lambda: ScoringConfig(50, 10, 20, 50, "scoring-v1")
    )
    max_recovery_attempts: int = 3
    attribution_window_seconds: int = 3_600

    def __post_init__(self) -> None:
        if not self.merchant_ids:
            raise ValueError("at least one merchant_id is required")
        if self.transaction_count <= 0:
            raise ValueError("transaction_count must be positive")
        if not self.amounts_minor_units or any(amount < 0 for amount in self.amounts_minor_units):
            raise ValueError("amounts_minor_units must contain non-negative values")
        if not self.payment_methods or not self.failure_codes:
            raise ValueError("payment_methods and failure_codes must not be empty")
        if self.event_types and len(self.event_types) != self.transaction_count:
            raise ValueError("event_types must contain one event type per transaction")
        if len(self.standard_currency) != 3:
            raise ValueError("standard_currency must be an ISO-like three-letter code")
        if self.high_value_indices and self.high_value_amount_minor_units is None:
            raise ValueError("high_value_amount_minor_units is required for high-value cases")
        if (
            self.high_value_amount_minor_units is not None
            and self.high_value_amount_minor_units < 0
        ):
            raise ValueError("high_value_amount_minor_units must be non-negative")
        scenario_sets = (
            self.high_value_indices,
            self.duplicate_event_indices,
            self.opt_out_indices,
            self.incident_indices,
            self.natural_recovery_indices,
            self.assisted_recovery_indices,
            self.provider_failure_indices,
        )
        if any(
            index < 0 or index >= self.transaction_count
            for values in scenario_sets
            for index in values
        ):
            raise ValueError("scenario indices must be within transaction_count")
        if self.natural_recovery_indices & self.assisted_recovery_indices:
            raise ValueError("natural and assisted recovery indices must not overlap")
        if self.max_recovery_attempts <= 0:
            raise ValueError("max_recovery_attempts must be positive")
        if self.attribution_window_seconds <= 0:
            raise ValueError("attribution_window_seconds must be positive")


@dataclass(frozen=True)
class SimulatorRunResult:
    seed: int
    label: str
    persisted_event_count: int
    duplicate_event_count: int
    case_count: int
    recommendation_count: int
    success_event_count: int
    scenario_counts: dict[str, int]
    event_ids: tuple[str, ...]
    case_ids: tuple[str, ...]


class SimulatorService:
    """Runs synthetic events through ingestion, case, scoring, and fallback paths."""

    provider_name = "simulator"

    def __init__(self, session: Session, config: SimulatorConfig) -> None:
        self.session = session
        self.config = config
        self._random = random.Random(config.seed)
        self._payment_provider = SimulatedPaymentProvider()

    def run(self) -> SimulatorRunResult:
        self._ensure_merchants()
        event_ids: list[str] = []
        case_ids: set[str] = set()
        duplicate_count = 0
        success_count = 0
        scenario_counts: dict[str, int] = {}
        ingester = EventIngestionService(self.session, self.provider_name)
        cases = RecoveryCaseService(
            self.session,
            self.provider_name,
            self.config.max_recovery_attempts,
        )
        for index in range(self.config.transaction_count):
            base_event = self._failure_event(index)
            result, case = self._process_event(ingester, cases, base_event)
            event_ids.append(base_event.event_id)
            if result.duplicate:
                duplicate_count += 1
            if case is not None and is_open(RecoveryCaseStatus(case.status)):
                case_ids.add(case.id)
            if index in self.config.duplicate_event_indices:
                duplicate_result, _ = self._process_event(ingester, cases, base_event)
                duplicate_count += int(duplicate_result.duplicate)
                scenario_counts["duplicate_event"] = scenario_counts.get("duplicate_event", 0) + 1
            if index in self.config.opt_out_indices:
                opt_out_event = self._opt_out_event(index, base_event)
                self._process_auxiliary_event(ingester, opt_out_event)
                event_ids.append(opt_out_event.event_id)
                scenario_counts["opt_out"] = scenario_counts.get("opt_out", 0) + 1
            if index in self.config.incident_indices:
                incident_event = self._incident_event(index, base_event)
                self._process_auxiliary_event(ingester, incident_event)
                event_ids.append(incident_event.event_id)
                scenario_counts["incident"] = scenario_counts.get("incident", 0) + 1
            recovery_kind = self._recovery_kind(index)
            if recovery_kind is not None:
                action_time = None
                if recovery_kind == "assisted_recovery" and case is not None:
                    action_time = self._execute_assisted_action(case, base_event.occurred_at)
                success_event = self._success_event(index, base_event, occurred_at=action_time)
                self._process_auxiliary_event(ingester, success_event)
                event_ids.append(success_event.event_id)
                success_count += 1
                scenario_counts[recovery_kind] = scenario_counts.get(recovery_kind, 0) + 1
            if index in self.config.provider_failure_indices:
                scenario_counts["provider_failure"] = scenario_counts.get("provider_failure", 0) + 1
            if index in self.config.high_value_indices:
                scenario_counts["high_value"] = scenario_counts.get("high_value", 0) + 1

        persisted_count = self._count_events(event_ids)
        recommendation_count = self._count_recommendations(case_ids)
        self._attribute_cases(case_ids)
        self._refresh_recovery_scenario_counts(scenario_counts)
        return SimulatorRunResult(
            seed=self.config.seed,
            label="synthetic_simulator_data",
            persisted_event_count=persisted_count,
            duplicate_event_count=duplicate_count,
            case_count=len(case_ids),
            recommendation_count=recommendation_count,
            success_event_count=success_count,
            scenario_counts=scenario_counts,
            event_ids=tuple(event_ids),
            case_ids=tuple(sorted(case_ids)),
        )

    def _process_event(
        self,
        ingester: EventIngestionService,
        cases: RecoveryCaseService,
        event: RevenueEvent,
    ) -> tuple[EventIngestionResult, RecoveryCase | None]:
        self.session.rollback()
        result = ingester.ingest(event)
        case = None
        if not result.duplicate and event.event_type in RECOVERABLE_EVENT_TYPES:
            case = cases.associate(event)
            if case is not None:
                case_id = case.id
                self.session.rollback()
                CaseAnalysisService(
                    self.session,
                    event.merchant_id,
                    self.config.scoring_config,
                ).analyze(case_id)
                self.session.rollback()
                AIRecommendationService(
                    self.session,
                    event.merchant_id,
                    provider=None,
                ).fallback(case_id)
        return result, case

    def _process_auxiliary_event(
        self, ingester: EventIngestionService, event: RevenueEvent
    ) -> None:
        self.session.rollback()
        result = ingester.ingest(event)
        if result.duplicate:
            return
        if event.event_type == RevenueEventType.CUSTOMER_OPTED_OUT:
            CustomerOptOutService(self.session, event.merchant_id, self.provider_name).apply(event)
            return
        if event.event_type != RevenueEventType.PAYMENT_SUCCEEDED:
            return
        if event.payment_id is None or event.amount_minor_units is None or event.currency is None:
            raise ValueError("simulated payment success requires payment identity and money")
        self._payment_provider.set_status(
            event.merchant_id,
            event.payment_id,
            PaymentStatus.SUCCEEDED,
            amount_minor_units=event.amount_minor_units,
            currency=event.currency,
            provider_reference=f"sim_payment_{event.payment_id}",
        )
        PaymentReconciliationService(
            self.session,
            event.merchant_id,
            self._payment_provider,
            provider_name=self.provider_name,
        ).reconcile(event)

    def _failure_event(self, index: int) -> RevenueEvent:
        merchant_id = self.config.merchant_ids[index % len(self.config.merchant_ids)]
        amount = (
            self.config.high_value_amount_minor_units
            if index in self.config.high_value_indices
            else self._random.choice(self.config.amounts_minor_units)
        )
        occurred_at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
        event_type = self.config.event_types[index] if self.config.event_types else None
        event_type = event_type or RevenueEventType.PAYMENT_FAILED
        obligation_type = {
            RevenueEventType.PAYMENT_FAILED: "payment",
            RevenueEventType.CHECKOUT_ABANDONED: "checkout",
            RevenueEventType.SUBSCRIPTION_PAYMENT_FAILED: "subscription",
            RevenueEventType.INVOICE_OVERDUE: "invoice",
        }.get(event_type)
        if obligation_type is None:
            raise ValueError(f"simulator event type is not recoverable: {event_type}")
        return RevenueEvent(
            event_id=f"sim-{self.config.seed}-failure-{index}",
            event_type=event_type,
            merchant_id=merchant_id,
            source_object_id=f"sim-order-{self.config.seed}-{index}",
            external_obligation_id=f"sim-order-{self.config.seed}-{index}",
            obligation_type=obligation_type,
            customer_external_id=f"sim-customer-{self.config.seed}-{index}",
            payment_id=f"sim-payment-{self.config.seed}-{index}",
            amount_minor_units=amount,
            currency=self.config.standard_currency.upper(),
            payment_method=self._random.choice(self.config.payment_methods),
            failure_code=self._random.choice(self.config.failure_codes),
            occurred_at=occurred_at,
            correlation_id=f"sim-correlation-{self.config.seed}-{index}",
        )

    def _opt_out_event(self, index: int, base_event: RevenueEvent) -> RevenueEvent:
        return self._simple_event(index, base_event, RevenueEventType.CUSTOMER_OPTED_OUT, "optout")

    def _incident_event(self, index: int, base_event: RevenueEvent) -> RevenueEvent:
        return self._simple_event(index, base_event, RevenueEventType.INCIDENT_DETECTED, "incident")

    def _success_event(
        self,
        index: int,
        base_event: RevenueEvent,
        *,
        occurred_at: datetime | None = None,
    ) -> RevenueEvent:
        return base_event.model_copy(
            update={
                "event_id": f"sim-{self.config.seed}-success-{index}",
                "event_type": (
                    RevenueEventType.INVOICE_PAID
                    if base_event.event_type == RevenueEventType.INVOICE_OVERDUE
                    else RevenueEventType.PAYMENT_SUCCEEDED
                ),
                # A success is a later state for the same provider payment
                # attempt, not a new payment identity. This keeps simulator
                # reconciliation aligned with the production event contract.
                "payment_id": base_event.payment_id,
                "failure_code": None,
                "occurred_at": occurred_at or base_event.occurred_at,
            }
        )

    def _execute_assisted_action(
        self, case: RecoveryCase | None, case_event_time: datetime
    ) -> datetime:
        if case is None:
            raise ValueError("assisted recovery requires an associated recovery case")
        merchant_id = case.merchant_id
        case_id = case.id
        self.session.rollback()
        active = PolicyService(self.session, merchant_id).active()
        if active is None:
            raise ValueError("assisted recovery requires an active merchant policy")
        # Keep synthetic action chronology inside the case attribution window. The
        # simulator must be reproducible even when it is run on a different day.
        action_time = case_event_time.astimezone(UTC) + timedelta(seconds=1)
        settings = get_settings()
        self._payment_provider.set_status(
            merchant_id,
            self._payment_id(case_id),
            PaymentStatus.FAILED,
        )
        result = ActionCommandService(
            self.session,
            merchant_id,
            JobConfig(
                max_attempts=self.config.max_recovery_attempts,
                lease_seconds=settings.job_lease_seconds,
                backoff_base_seconds=settings.job_backoff_base_seconds,
                backoff_max_seconds=settings.job_backoff_max_seconds,
            ),
        ).request(
            case_id=case_id,
            action_type=ActionType.SEND_EMAIL,
            idempotency_key=f"sim-{self.config.seed}-assisted-{case_id}",
            due_at=action_time,
            actor_id="simulator",
            actor_role="ADMIN",
        )
        if result.status != ActionCommandStatus.SCHEDULED:
            raise ValueError(f"assisted recovery policy did not schedule action: {result.reason}")
        self.session.rollback()
        worker = WorkerService(
            self.session,
            merchant_id,
            JobService(
                self.session,
                merchant_id,
                JobConfig(
                    max_attempts=self.config.max_recovery_attempts,
                    lease_seconds=settings.job_lease_seconds,
                    backoff_base_seconds=settings.job_backoff_base_seconds,
                    backoff_max_seconds=settings.job_backoff_max_seconds,
                ),
            ),
            ProviderActionExecutor(
                payment=self._payment_provider,
                messaging=SimulatedMessagingProvider(),
                merchant_id=merchant_id,
            ),
            ProviderPreflightChecker(self.session, merchant_id, self._payment_provider),
        )
        execution = worker.process_once(now=action_time)
        if execution.status != "succeeded":
            raise ValueError(f"assisted recovery action did not execute: {execution.reason_code}")
        return action_time

    def _payment_id(self, case_id: str) -> str:
        payment = self.session.scalar(
            select(PaymentAttempt.external_payment_id).where(
                PaymentAttempt.merchant_id.in_(self.config.merchant_ids),
                PaymentAttempt.recovery_case_id == case_id,
            )
        )
        if payment is None:
            raise ValueError("assisted recovery case has no payment identity")
        return payment

    def _simple_event(
        self,
        index: int,
        base_event: RevenueEvent,
        event_type: RevenueEventType,
        suffix: str,
    ) -> RevenueEvent:
        return RevenueEvent(
            event_id=f"sim-{self.config.seed}-{suffix}-{index}",
            event_type=event_type,
            merchant_id=base_event.merchant_id,
            source_object_id=f"sim-{suffix}-{self.config.seed}-{index}",
            customer_external_id=base_event.customer_external_id,
            occurred_at=base_event.occurred_at,
            correlation_id=f"sim-correlation-{self.config.seed}-{suffix}-{index}",
        )

    def _recovery_kind(self, index: int) -> str | None:
        if index in self.config.natural_recovery_indices:
            return "natural_recovery"
        if index in self.config.assisted_recovery_indices:
            return "assisted_recovery"
        return None

    def _ensure_merchants(self) -> None:
        with self.session.begin():
            for merchant_id in self.config.merchant_ids:
                merchant = self.session.scalar(select(Merchant).where(Merchant.id == merchant_id))
                if merchant is None:
                    self.session.add(
                        Merchant(
                            id=merchant_id,
                            external_key=f"simulator:{merchant_id}",
                            name=f"Synthetic {merchant_id}",
                            default_currency=self.config.standard_currency.upper(),
                            timezone="UTC",
                            environment_mode="simulator",
                            status="active",
                        )
                    )

    def _count_events(self, event_ids: list[str]) -> int:
        if not event_ids:
            return 0
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(RevenueEventRecord)
                .where(
                    RevenueEventRecord.merchant_id.in_(self.config.merchant_ids),
                    RevenueEventRecord.external_event_id.in_(event_ids),
                )
            )
            or 0
        )

    def _count_recommendations(self, case_ids: set[str]) -> int:
        if not case_ids:
            return 0
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(Recommendation)
                .where(
                    Recommendation.merchant_id.in_(self.config.merchant_ids),
                    Recommendation.recovery_case_id.in_(case_ids),
                )
            )
            or 0
        )

    def _attribute_cases(self, case_ids: set[str]) -> None:
        now = datetime.now(UTC)
        for case_id in sorted(case_ids):
            case = self.session.scalar(
                select(RecoveryCase).where(
                    RecoveryCase.id == case_id,
                    RecoveryCase.merchant_id.in_(self.config.merchant_ids),
                )
            )
            if case is None:
                continue
            AttributionService(
                self.session,
                case.merchant_id,
                AttributionConfig(timedelta(seconds=self.config.attribution_window_seconds)),
            ).attribute_case(case_id, now=now, correlation_id=f"sim-attribution-{self.config.seed}")

    def _refresh_recovery_scenario_counts(self, scenario_counts: dict[str, int]) -> None:
        records = self.session.scalars(
            select(AttributionRecord).where(
                AttributionRecord.merchant_id.in_(self.config.merchant_ids),
                AttributionRecord.outcome.in_(
                    ["NATURAL_RECOVERY", "ASSISTED_RECOVERY"]
                ),
            )
        ).all()
        natural = sum(record.outcome == "NATURAL_RECOVERY" for record in records)
        assisted = sum(record.outcome == "ASSISTED_RECOVERY" for record in records)
        if natural:
            scenario_counts["natural_recovery"] = natural
        else:
            scenario_counts.pop("natural_recovery", None)
        if assisted:
            scenario_counts["assisted_recovery"] = assisted
        else:
            scenario_counts.pop("assisted_recovery", None)
