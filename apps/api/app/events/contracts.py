from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RevenueEventType(StrEnum):
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_REFUNDED = "payment.refunded"
    PAYMENT_REVERSED = "payment.reversed"
    CHECKOUT_STARTED = "checkout.started"
    CHECKOUT_ABANDONED = "checkout.abandoned"
    SUBSCRIPTION_PAYMENT_FAILED = "subscription.payment_failed"
    INVOICE_OVERDUE = "invoice.overdue"
    INVOICE_PAID = "invoice.paid"
    CUSTOMER_OPTED_OUT = "customer.opted_out"
    MESSAGE_DELIVERED = "message.delivered"
    MESSAGE_OPENED = "message.opened"
    MESSAGE_CLICKED = "message.clicked"
    ACTION_FAILED = "action.failed"
    INCIDENT_DETECTED = "incident.detected"
    INCIDENT_RESOLVED = "incident.resolved"


class RevenueEvent(BaseModel):
    """Provider-neutral, signed event contract at the ingestion boundary."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=255)
    event_type: RevenueEventType
    merchant_id: str = Field(min_length=1, max_length=255)
    source_object_id: str = Field(min_length=1, max_length=255)
    external_obligation_id: str | None = Field(default=None, max_length=255)
    obligation_type: str | None = Field(default=None, max_length=64)
    customer_external_id: str | None = Field(default=None, max_length=255)
    payment_id: str | None = Field(default=None, max_length=255)
    amount_minor_units: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    payment_method: str | None = Field(default=None, max_length=64)
    failure_code: str | None = Field(default=None, max_length=128)
    occurred_at: datetime
    correlation_id: str | None = Field(default=None, max_length=128)
    payload_version: str = Field(default="1", min_length=1, max_length=32)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_money_pair(self) -> "RevenueEvent":
        if (self.amount_minor_units is None) != (self.currency is None):
            raise ValueError("amount_minor_units and currency must be provided together")
        return self


class EventIngestionResult(BaseModel):
    event_id: str
    status: str
    duplicate: bool
    correlation_id: str
