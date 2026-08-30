from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class ProviderHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class PaymentStatus(StrEnum):
    UNKNOWN = "unknown"
    PENDING = "pending"
    FAILED = "failed"
    SUCCEEDED = "succeeded"


class DeliveryStatus(StrEnum):
    ACCEPTED = "accepted"
    DELIVERED = "delivered"
    FAILED = "failed"


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    status: ProviderHealthStatus
    detail: str


@dataclass(frozen=True)
class PaymentStatusSnapshot:
    external_payment_id: str
    status: PaymentStatus
    amount_minor_units: int | None
    currency: str | None
    provider_reference: str | None
    observed_at: datetime

    def __post_init__(self) -> None:
        if not self.external_payment_id:
            raise ValueError("external_payment_id is required")
        if self.amount_minor_units is not None and self.amount_minor_units < 0:
            raise ValueError("amount_minor_units must be non-negative")
        if self.currency is not None and len(self.currency) != 3:
            raise ValueError("currency must be an ISO-like three-letter code")


@dataclass(frozen=True)
class PaymentLinkRequest:
    merchant_id: str
    obligation_id: str
    amount_minor_units: int
    currency: str
    idempotency_key: str

    def __post_init__(self) -> None:
        if not self.merchant_id or not self.obligation_id or not self.idempotency_key:
            raise ValueError("payment link identity fields are required")
        if self.amount_minor_units < 0:
            raise ValueError("amount_minor_units must be non-negative")
        if len(self.currency) != 3:
            raise ValueError("currency must be an ISO-like three-letter code")


@dataclass(frozen=True)
class PaymentLinkResult:
    provider_reference: str
    url: str | None
    reused: bool

    def __post_init__(self) -> None:
        if not self.provider_reference:
            raise ValueError("provider_reference is required")


@dataclass(frozen=True)
class MessageRequest:
    merchant_id: str
    channel: str
    recipient_external_id: str
    case_id: str
    idempotency_key: str
    template_key: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.merchant_id,
                self.channel,
                self.recipient_external_id,
                self.case_id,
                self.idempotency_key,
                self.template_key,
            )
        ):
            raise ValueError("message identity fields are required")


@dataclass(frozen=True)
class DeliveryResult:
    status: DeliveryStatus
    provider_reference: str | None
    cost_minor_units: int
    reused: bool

    def __post_init__(self) -> None:
        if self.cost_minor_units < 0:
            raise ValueError("cost_minor_units must be non-negative")


class PaymentProvider(Protocol):
    def get_payment_status(
        self, merchant_id: str, external_payment_id: str
    ) -> PaymentStatusSnapshot:
        """Return provider-confirmed payment state for reconciliation/preflight."""

    def create_retry_link(self, request: PaymentLinkRequest) -> PaymentLinkResult:
        """Create or idempotently reuse a permitted payment recovery link."""

    def health(self) -> ProviderHealth:
        """Return safe provider health without exposing credentials or payloads."""


class MessagingProvider(Protocol):
    def send(self, request: MessageRequest) -> DeliveryResult:
        """Send one approved message effect for the supplied idempotency key."""

    def health(self) -> ProviderHealth:
        """Return safe provider health without exposing recipient content."""


class JobScheduler(Protocol):
    def schedule_action(self, **kwargs: object) -> object:
        """Persist a durable action job through the scheduler application boundary."""

    def cancel(self, job_id: str, *, reason: str, correlation_id: str = "job-cancel") -> object:
        """Cancel a durable job without creating a provider effect."""
