from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.base import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Role(StrEnum):
    VIEWER = "VIEWER"
    OPERATOR = "OPERATOR"
    ADMIN = "ADMIN"


class RecoveryCaseStatus(StrEnum):
    DETECTED = "DETECTED"
    ANALYZING = "ANALYZING"
    ACTION_PENDING = "ACTION_PENDING"
    POLICY_CHECK = "POLICY_CHECK"
    SCHEDULED = "SCHEDULED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    WAITING = "WAITING"
    RECOVERED = "RECOVERED"
    ESCALATED = "ESCALATED"
    EXHAUSTED = "EXHAUSTED"
    CANCELLED = "CANCELLED"
    OPTED_OUT = "OPTED_OUT"
    SUPPRESSED = "SUPPRESSED"


class ProcessingStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class JobStatus(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    DEAD_LETTERED = "DEAD_LETTERED"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class Merchant(TimestampMixin, Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    external_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    environment_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    email_or_label: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    __table_args__ = (UniqueConstraint("issuer", "subject", name="uq_users_issuer_subject"),)


class MerchantMembership(Base):
    __tablename__ = "merchant_memberships"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    external_customer_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime)
    __table_args__ = (
        UniqueConstraint(
            "merchant_id", "external_customer_id", name="uq_customers_merchant_external"
        ),
    )


class Obligation(TimestampMixin, Base):
    __tablename__ = "obligations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    obligation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    external_obligation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(255))
    checkout_intent_id: Mapped[str | None] = mapped_column(String(255))
    subscription_id: Mapped[str | None] = mapped_column(String(255))
    billing_cycle_id: Mapped[str | None] = mapped_column(String(255))
    invoice_id: Mapped[str | None] = mapped_column(String(255))
    amount_at_risk: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    authoritative_status: Mapped[str] = mapped_column(String(32), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    __table_args__ = (
        UniqueConstraint(
            "merchant_id",
            "obligation_type",
            "external_obligation_id",
            name="uq_obligations_identity",
        ),
        Index("ix_obligations_merchant_status", "merchant_id", "status"),
        CheckConstraint("amount_at_risk >= 0", name="ck_obligations_amount_nonnegative"),
        CheckConstraint("length(currency) = 3", name="ck_obligations_currency_code"),
    )


class RecoveryCase(TimestampMixin, Base):
    __tablename__ = "recovery_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"))
    obligation_id: Mapped[str] = mapped_column(
        ForeignKey("obligations.id"), unique=True, nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    root_cause: Mapped[str | None] = mapped_column(String(128))
    root_cause_confidence: Mapped[int | None] = mapped_column(Integer)
    recovery_probability: Mapped[int | None] = mapped_column(Integer)
    probability_version: Mapped[str | None] = mapped_column(String(64))
    expected_recoverable_amount: Mapped[int | None] = mapped_column(BigInteger)
    priority_score: Mapped[int | None] = mapped_column(Integer)
    priority_version: Mapped[str | None] = mapped_column(String(64))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    recovered_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    attribution_status: Mapped[str] = mapped_column(String(32), nullable=False)
    incident_suppressed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    __table_args__ = (
        Index("ix_cases_merchant_status", "merchant_id", "status"),
        Index("ix_cases_merchant_priority", "merchant_id", "priority_score"),
        Index("ix_cases_merchant_customer", "merchant_id", "customer_id"),
        CheckConstraint("recovered_amount >= 0", name="ck_cases_recovered_amount_nonnegative"),
        CheckConstraint("length(currency) = 3", name="ck_cases_currency_code"),
    )


class PaymentAttempt(TimestampMixin, Base):
    __tablename__ = "payment_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False)
    external_payment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(128))
    provider_event_at: Mapped[datetime | None] = mapped_column(DateTime)
    __table_args__ = (
        UniqueConstraint(
            "merchant_id", "provider", "external_payment_id", name="uq_payment_identity"
        ),
        CheckConstraint("amount >= 0", name="ck_payment_attempts_amount_nonnegative"),
        CheckConstraint("length(currency) = 3", name="ck_payment_attempts_currency_code"),
    )


class RevenueEvent(TimestampMixin, Base):
    __tablename__ = "revenue_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    source_object_id: Mapped[str] = mapped_column(String(255), nullable=False)
    obligation_id: Mapped[str | None] = mapped_column(ForeignKey("obligations.id"))
    recovery_case_id: Mapped[str | None] = mapped_column(ForeignKey("recovery_cases.id"))
    normalized_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    provider_event_at: Mapped[datetime | None] = mapped_column(DateTime)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "merchant_id", "provider", "external_event_id", name="uq_revenue_event_identity"
        ),
        Index("ix_revenue_events_unprocessed", "merchant_id", "processing_status", "received_at"),
    )


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "merchant_id", "provider", "idempotency_key", name="uq_processed_event_key"
        ),
    )


class Recommendation(TimestampMixin, Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(128), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    model_version: Mapped[str | None] = mapped_column(String(128))
    scoring_version: Mapped[str] = mapped_column(String(64), nullable=False)


class MerchantPolicy(TimestampMixin, Base):
    __tablename__ = "merchant_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(
        ForeignKey("merchants.id"), unique=True, nullable=False
    )
    current_version_id: Mapped[str | None] = mapped_column(ForeignKey("policy_versions.id"))


class PolicyVersion(Base):
    __tablename__ = "policy_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    __table_args__ = (UniqueConstraint("merchant_id", "version", name="uq_policy_version"),)


class PolicyDecision(Base):
    __tablename__ = "policy_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False)
    recommendation_id: Mapped[str | None] = mapped_column(ForeignKey("recommendations.id"))
    policy_version_id: Mapped[str] = mapped_column(ForeignKey("policy_versions.id"), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    decisive_rule: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    input_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False)
    recommendation_id: Mapped[str | None] = mapped_column(ForeignKey("recommendations.id"))
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(255))
    cost_minor_units: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    failure_category: Mapped[str | None] = mapped_column(String(64))
    failure_detail_safe: Mapped[str | None] = mapped_column(String(512))
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    __table_args__ = (
        UniqueConstraint("merchant_id", "idempotency_key", name="uq_action_idempotency"),
        CheckConstraint("cost_minor_units >= 0", name="ck_actions_cost_nonnegative"),
    )


class ScheduledJob(TimestampMixin, Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    recovery_case_id: Mapped[str | None] = mapped_column(ForeignKey("recovery_cases.id"))
    recovery_action_id: Mapped[str | None] = mapped_column(ForeignKey("recovery_actions.id"))
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    last_error_category: Mapped[str | None] = mapped_column(String(64))
    last_error_safe: Mapped[str | None] = mapped_column(String(512))
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    __table_args__ = (
        UniqueConstraint("merchant_id", "idempotency_key", name="uq_job_idempotency"),
        Index("ix_jobs_due", "merchant_id", "status", "due_at"),
    )


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    dimension_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    baseline_window: Mapped[dict] = mapped_column(JSON, nullable=False)
    current_window: Mapped[dict] = mapped_column(JSON, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    detector_version: Mapped[str] = mapped_column(String(64), nullable=False)


class CaseIncident(Base):
    __tablename__ = "case_incidents"

    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), primary_key=True)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), primary_key=True)
    association_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    control_ratio: Mapped[int] = mapped_column(Integer, nullable=False)
    treatment_ratio: Mapped[int] = mapped_column(Integer, nullable=False)
    attribution_window: Mapped[dict] = mapped_column(JSON, nullable=False)
    eligibility_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class ExperimentAssignment(Base):
    __tablename__ = "experiment_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    recovery_case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), nullable=False)
    variant: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    assignment_version: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        UniqueConstraint("experiment_id", "recovery_case_id", name="uq_experiment_assignment"),
    )


class AttributionRecord(TimestampMixin, Base):
    __tablename__ = "attribution_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    recovery_case_id: Mapped[str] = mapped_column(
        ForeignKey("recovery_cases.id"), unique=True, nullable=False
    )
    experiment_assignment_id: Mapped[str | None] = mapped_column(
        ForeignKey("experiment_assignments.id")
    )
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    qualifying_action_id: Mapped[str | None] = mapped_column(ForeignKey("recovery_actions.id"))
    attribution_window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attribution_window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    verified_payment_id: Mapped[str | None] = mapped_column(String(255))
    recovered_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    adjustment_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    confidence: Mapped[int | None] = mapped_column(Integer)
    limitations: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("recovered_amount >= 0", name="ck_attribution_recovered_nonnegative"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(128))
    from_state: Mapped[str | None] = mapped_column(String(32))
    to_state: Mapped[str | None] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_safe_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    __table_args__ = (
        Index("ix_audit_entity_time", "merchant_id", "entity_type", "entity_id", "created_at"),
    )
