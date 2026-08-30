from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import UTC, datetime
from typing import Any

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
from app.integrations.errors import (
    ProviderAmbiguousError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderTransportError,
)

Transport = Callable[[dict[str, Any]], object]


class TransportPaymentProvider(PaymentProvider):
    """Maps provider-specific transport payloads to the canonical payment contract."""

    def __init__(
        self,
        *,
        provider: str,
        status_transport: Transport,
        link_transport: Transport,
        timeout_seconds: float,
    ) -> None:
        self.provider = _required_name(provider, "provider")
        self.status_transport = status_transport
        self.link_transport = link_transport
        self.timeout_seconds = _positive_timeout(timeout_seconds)

    def get_payment_status(
        self, merchant_id: str, external_payment_id: str
    ) -> PaymentStatusSnapshot:
        if not merchant_id or not external_payment_id:
            raise ValueError("merchant_id and external_payment_id are required")
        raw = self._call(
            self.status_transport,
            {"merchant_id": merchant_id, "payment_id": external_payment_id},
        )
        if not isinstance(raw, Mapping):
            raise ProviderResponseError(self.provider)
        try:
            status = PaymentStatus(str(raw["status"]).lower())
            amount = raw.get("amount_minor_units")
            if amount is not None and (isinstance(amount, bool) or not isinstance(amount, int)):
                raise TypeError
            currency = raw.get("currency")
            if currency is not None and not isinstance(currency, str):
                raise TypeError
            reference = raw.get("provider_reference")
            if reference is not None and not isinstance(reference, str):
                raise TypeError
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderResponseError(self.provider) from exc
        return PaymentStatusSnapshot(
            external_payment_id=external_payment_id,
            status=status,
            amount_minor_units=amount,
            currency=currency.upper() if currency is not None else None,
            provider_reference=reference,
            observed_at=datetime.now(UTC),
        )

    def create_retry_link(self, request: PaymentLinkRequest) -> PaymentLinkResult:
        raw = self._call(
            self.link_transport,
            {
                "merchant_id": request.merchant_id,
                "obligation_id": request.obligation_id,
                "amount_minor_units": request.amount_minor_units,
                "currency": request.currency,
                "idempotency_key": request.idempotency_key,
            },
        )
        if not isinstance(raw, Mapping):
            raise ProviderResponseError(self.provider)
        reference = raw.get("provider_reference")
        url = raw.get("url")
        if not isinstance(reference, str) or not reference:
            # A timeout or malformed response must never be treated as a reusable
            # provider reference. The caller must reconcile before another effect.
            raise ProviderAmbiguousError(self.provider)
        if url is not None and not isinstance(url, str):
            raise ProviderResponseError(self.provider)
        return PaymentLinkResult(reference, url, bool(raw.get("reused", False)))

    def health(self) -> ProviderHealth:
        return ProviderHealth(self.provider, ProviderHealthStatus.HEALTHY, "configured")

    def _call(self, transport: Transport, payload: dict[str, Any]) -> object:
        executor = ThreadPoolExecutor(max_workers=1)
        future: Future[object] = executor.submit(transport, payload)
        try:
            return future.result(timeout=self.timeout_seconds)
        except FutureTimeout as exc:
            future.cancel()
            raise ProviderTimeoutError(self.provider) from exc
        except ProviderError:
            raise
        except Exception as exc:
            category = str(getattr(exc, "category", ""))
            if category == "rate_limited":
                raise ProviderRateLimitError(self.provider) from exc
            raise ProviderTransportError(self.provider) from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)


class TransportMessagingProvider(MessagingProvider):
    """Maps provider-specific messaging responses to a safe delivery contract."""

    def __init__(
        self,
        *,
        provider: str,
        send_transport: Transport,
        timeout_seconds: float,
    ) -> None:
        self.provider = _required_name(provider, "provider")
        self.send_transport = send_transport
        self.timeout_seconds = _positive_timeout(timeout_seconds)

    def send(self, request: MessageRequest) -> DeliveryResult:
        raw = self._call(
            {
                "merchant_id": request.merchant_id,
                "channel": request.channel,
                "recipient_external_id": request.recipient_external_id,
                "case_id": request.case_id,
                "idempotency_key": request.idempotency_key,
                "template_key": request.template_key,
            }
        )
        if not isinstance(raw, Mapping):
            raise ProviderResponseError(self.provider)
        try:
            result = DeliveryResult(
                status=DeliveryStatus(str(raw["status"]).lower()),
                provider_reference=_optional_string(raw.get("provider_reference")),
                cost_minor_units=_nonnegative_int(raw.get("cost_minor_units", 0)),
                reused=bool(raw.get("reused", False)),
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise ProviderResponseError(self.provider) from exc
        if result.status != DeliveryStatus.FAILED and result.provider_reference is None:
            raise ProviderAmbiguousError(self.provider)
        return result

    def health(self) -> ProviderHealth:
        return ProviderHealth(self.provider, ProviderHealthStatus.HEALTHY, "configured")

    def _call(self, payload: dict[str, Any]) -> object:
        executor = ThreadPoolExecutor(max_workers=1)
        future: Future[object] = executor.submit(self.send_transport, payload)
        try:
            return future.result(timeout=self.timeout_seconds)
        except FutureTimeout as exc:
            future.cancel()
            raise ProviderTimeoutError(self.provider) from exc
        except ProviderError:
            raise
        except Exception as exc:
            category = str(getattr(exc, "category", ""))
            if category == "rate_limited":
                raise ProviderRateLimitError(self.provider) from exc
            raise ProviderTransportError(self.provider) from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)


def _required_name(value: str, field: str) -> str:
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _positive_timeout(value: float) -> float:
    if value <= 0:
        raise ValueError("timeout_seconds must be positive")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    return value


def _nonnegative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("value must be a non-negative integer")
    return value
