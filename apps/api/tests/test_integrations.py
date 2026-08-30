from __future__ import annotations

import time

import pytest

from app.integrations.contracts import (
    DeliveryResult,
    DeliveryStatus,
    MessageRequest,
    PaymentLinkRequest,
    PaymentStatus,
)
from app.integrations.errors import (
    ProviderResponseError,
    ProviderTimeoutError,
)
from app.integrations.executor import ProviderActionExecutor
from app.integrations.simulated import SimulatedMessagingProvider, SimulatedPaymentProvider
from app.integrations.transport import TransportMessagingProvider, TransportPaymentProvider
from app.workers.contracts import ActionExecutionError, WorkItem


def payment_link_request() -> PaymentLinkRequest:
    return PaymentLinkRequest(
        merchant_id="merchant-1",
        obligation_id="obligation-1",
        amount_minor_units=249_900,
        currency="INR",
        idempotency_key="action-1",
    )


def work_item(action_type: str, *, customer: str | None = "cust-1") -> WorkItem:
    return WorkItem(
        job_id="job-1",
        action_id="action-1",
        case_id="case-1",
        action_type=action_type,
        action_idempotency_key="action-key-1",
        policy_version_id="policy-version-1",
        case_status="SCHEDULED",
        customer_external_id=customer,
        obligation_id="obligation-1",
        amount_minor_units=249_900,
        currency="INR",
        payment_id="pay-1",
    )


def test_transport_payment_provider_normalizes_status_and_link() -> None:
    calls: list[dict[str, object]] = []

    def status_transport(payload: dict[str, object]) -> object:
        calls.append(payload)
        return {
            "status": "SUCCEEDED",
            "amount_minor_units": 249_900,
            "currency": "inr",
            "provider_reference": "pay-ref-1",
        }

    provider = TransportPaymentProvider(
        provider="razorpay-test",
        status_transport=status_transport,
        link_transport=lambda payload: {
            "provider_reference": "link-ref-1",
            "url": "https://pay.example/link-1",
        },
        timeout_seconds=1,
    )
    snapshot = provider.get_payment_status("merchant-1", "pay-1")
    link = provider.create_retry_link(payment_link_request())

    assert snapshot.status == PaymentStatus.SUCCEEDED
    assert snapshot.currency == "INR"
    assert snapshot.provider_reference == "pay-ref-1"
    assert link.provider_reference == "link-ref-1"
    assert calls == [{"merchant_id": "merchant-1", "payment_id": "pay-1"}]
    assert provider.health().status == "healthy"


def test_transport_provider_rejects_malformed_and_times_out_safely() -> None:
    invalid = TransportPaymentProvider(
        provider="payment",
        status_transport=lambda payload: {"status": "not-a-payment-state"},
        link_transport=lambda payload: {},
        timeout_seconds=1,
    )
    with pytest.raises(ProviderResponseError):
        invalid.get_payment_status("merchant-1", "pay-1")
    with pytest.raises(ProviderTimeoutError):
        TransportMessagingProvider(
            provider="messaging",
            send_transport=lambda payload: (time.sleep(0.03), {})[1],
            timeout_seconds=0.001,
        ).send(
            MessageRequest(
                merchant_id="merchant-1",
                channel="email",
                recipient_external_id="cust-1",
                case_id="case-1",
                idempotency_key="action-1",
                template_key="recovery_payment_prompt",
            )
        )


def test_transport_messaging_provider_normalizes_delivery_and_cost() -> None:
    provider = TransportMessagingProvider(
        provider="messaging-test",
        send_transport=lambda payload: {
            "status": "DELIVERED",
            "provider_reference": "msg-1",
            "cost_minor_units": 25,
        },
        timeout_seconds=1,
    )
    result = provider.send(
        MessageRequest(
            merchant_id="merchant-1",
            channel="email",
            recipient_external_id="cust-1",
            case_id="case-1",
            idempotency_key="action-1",
            template_key="recovery_payment_prompt",
        )
    )
    assert result.status == DeliveryStatus.DELIVERED
    assert result.cost_minor_units == 25
    assert provider.health().status == "healthy"


def test_simulated_providers_are_labeled_and_idempotent() -> None:
    payment = SimulatedPaymentProvider()
    first_link = payment.create_retry_link(payment_link_request())
    second_link = payment.create_retry_link(payment_link_request())
    payment.set_status("merchant-1", "pay-1", PaymentStatus.FAILED)
    snapshot = payment.get_payment_status("merchant-1", "pay-1")

    messaging = SimulatedMessagingProvider()
    request = MessageRequest(
        merchant_id="merchant-1",
        channel="email",
        recipient_external_id="cust-1",
        case_id="case-1",
        idempotency_key="action-1",
        template_key="recovery_payment_prompt",
    )
    first_message = messaging.send(request)
    second_message = messaging.send(request)

    assert first_link.reused is False
    assert second_link.reused is True
    assert snapshot.status == PaymentStatus.FAILED
    assert first_message.reused is False
    assert second_message.reused is True
    assert messaging.health().detail == "synthetic provider"


def test_provider_action_executor_routes_registered_actions() -> None:
    payment = SimulatedPaymentProvider()
    payment.set_status("merchant-1", "pay-1", PaymentStatus.FAILED)
    messaging = SimulatedMessagingProvider()
    executor = ProviderActionExecutor(
        payment=payment,
        messaging=messaging,
        merchant_id="merchant-1",
    )

    link_result = executor.execute(work_item("GENERATE_PAYMENT_LINK"))
    message_result = executor.execute(work_item("SEND_EMAIL"))

    assert link_result.provider_reference == "sim_link_1"
    assert message_result.provider_reference == "sim_msg_1"
    assert message_result.cost_minor_units == 0


def test_provider_action_executor_rejects_missing_recipient_and_unregistered_action() -> None:
    executor = ProviderActionExecutor(
        payment=SimulatedPaymentProvider(),
        messaging=SimulatedMessagingProvider(),
        merchant_id="merchant-1",
    )
    with pytest.raises(ActionExecutionError, match="customer contact is unavailable"):
        executor.execute(work_item("SEND_EMAIL", customer=None))
    with pytest.raises(ActionExecutionError, match="not supported"):
        executor.execute(work_item("NOTIFY_ACCOUNT_MANAGER"))


def test_provider_action_executor_rechecks_payment_before_customer_effect() -> None:
    class RecordingMessagingProvider(SimulatedMessagingProvider):
        def __init__(self) -> None:
            super().__init__()
            self.send_calls = 0

        def send(self, request: MessageRequest) -> DeliveryResult:
            self.send_calls += 1
            return super().send(request)

    payment = SimulatedPaymentProvider()
    payment.set_status(
        "merchant-1",
        "pay-1",
        PaymentStatus.SUCCEEDED,
        amount_minor_units=249_900,
        currency="INR",
    )
    messaging = RecordingMessagingProvider()
    executor = ProviderActionExecutor(
        payment=payment,
        messaging=messaging,
        merchant_id="merchant-1",
    )

    with pytest.raises(ActionExecutionError, match="no longer outstanding"):
        executor.execute(work_item("SEND_EMAIL"))

    assert messaging.send_calls == 0


def test_provider_action_executor_maps_typed_provider_failure() -> None:
    payment = SimulatedPaymentProvider()
    payment.available = False
    executor = ProviderActionExecutor(
        payment=payment,
        messaging=SimulatedMessagingProvider(),
        merchant_id="merchant-1",
    )
    with pytest.raises(ActionExecutionError, match="simulated payment provider unavailable"):
        executor.execute(work_item("GENERATE_PAYMENT_LINK"))
