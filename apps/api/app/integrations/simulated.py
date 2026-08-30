from __future__ import annotations

from datetime import UTC, datetime

from app.integrations.contracts import (
    DeliveryResult,
    DeliveryStatus,
    MessageRequest,
    MessagingProvider,
    PaymentLinkRequest,
    PaymentLinkResult,
    PaymentProvider,
    PaymentStatus,
    PaymentStatusSnapshot,
    ProviderHealth,
    ProviderHealthStatus,
)
from app.integrations.errors import ProviderError


class SimulatedPaymentProvider(PaymentProvider):
    """Deterministic payment double; it never represents a real provider result."""

    def __init__(self, *, base_url: str = "https://simulator.recoveryos.test/pay") -> None:
        if not base_url:
            raise ValueError("base_url is required")
        self.base_url = base_url.rstrip("/")
        self._statuses: dict[tuple[str, str], PaymentStatusSnapshot] = {}
        self._links: dict[tuple[str, str], PaymentLinkResult] = {}
        self.available = True

    def set_status(
        self,
        merchant_id: str,
        external_payment_id: str,
        status: PaymentStatus,
        *,
        amount_minor_units: int | None = None,
        currency: str | None = None,
        provider_reference: str | None = None,
    ) -> None:
        self._statuses[(merchant_id, external_payment_id)] = PaymentStatusSnapshot(
            external_payment_id=external_payment_id,
            status=status,
            amount_minor_units=amount_minor_units,
            currency=currency.upper() if currency is not None else None,
            provider_reference=provider_reference,
            observed_at=datetime.now(UTC),
        )

    def get_payment_status(
        self, merchant_id: str, external_payment_id: str
    ) -> PaymentStatusSnapshot:
        self._ensure_available()
        snapshot = self._statuses.get((merchant_id, external_payment_id))
        if snapshot is None:
            return PaymentStatusSnapshot(
                external_payment_id=external_payment_id,
                status=PaymentStatus.UNKNOWN,
                amount_minor_units=None,
                currency=None,
                provider_reference=None,
                observed_at=datetime.now(UTC),
            )
        return snapshot

    def create_retry_link(self, request: PaymentLinkRequest) -> PaymentLinkResult:
        self._ensure_available()
        key = (request.merchant_id, request.idempotency_key)
        existing = self._links.get(key)
        if existing is not None:
            return PaymentLinkResult(existing.provider_reference, existing.url, True)
        result = PaymentLinkResult(
            provider_reference=f"sim_link_{len(self._links) + 1}",
            url=f"{self.base_url}/{request.idempotency_key}",
            reused=False,
        )
        self._links[key] = result
        return result

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            "simulated-payment",
            ProviderHealthStatus.HEALTHY if self.available else ProviderHealthStatus.UNAVAILABLE,
            "synthetic provider" if self.available else "simulated provider disabled",
        )

    def _ensure_available(self) -> None:
        if not self.available:
            raise ProviderError(
                "simulated_payment_unavailable",
                "simulated payment provider unavailable",
                retryable=True,
            )


class SimulatedMessagingProvider(MessagingProvider):
    """Deterministic messaging double with per-request idempotency."""

    def __init__(self) -> None:
        self.available = True
        self._results: dict[tuple[str, str], DeliveryResult] = {}
        self._sequence: list[DeliveryResult | ProviderError] = []

    def queue_outcome(self, outcome: DeliveryResult | ProviderError) -> None:
        self._sequence.append(outcome)

    def send(self, request: MessageRequest) -> DeliveryResult:
        if not self.available:
            raise ProviderError(
                "simulated_messaging_unavailable",
                "simulated messaging provider unavailable",
                retryable=True,
            )
        key = (request.merchant_id, request.idempotency_key)
        existing = self._results.get(key)
        if existing is not None:
            return DeliveryResult(
                existing.status,
                existing.provider_reference,
                existing.cost_minor_units,
                True,
            )
        outcome = (
            self._sequence.pop(0)
            if self._sequence
            else DeliveryResult(
                DeliveryStatus.DELIVERED,
                f"sim_msg_{len(self._results) + 1}",
                0,
                False,
            )
        )
        if isinstance(outcome, ProviderError):
            raise outcome
        if outcome.status != DeliveryStatus.FAILED and outcome.provider_reference is None:
            raise ProviderError(
                "simulated_messaging_ambiguous",
                "simulated messaging result requires reconciliation",
                retryable=True,
            )
        self._results[key] = outcome
        return outcome

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            "simulated-messaging",
            ProviderHealthStatus.HEALTHY if self.available else ProviderHealthStatus.UNAVAILABLE,
            "synthetic provider" if self.available else "simulated provider disabled",
        )
