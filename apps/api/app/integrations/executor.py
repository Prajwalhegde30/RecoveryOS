from __future__ import annotations

from app.integrations.contracts import (
    MessageRequest,
    MessagingProvider,
    PaymentLinkRequest,
    PaymentProvider,
    PaymentStatus,
)
from app.integrations.errors import ProviderError
from app.workers.contracts import (
    ActionExecutionError,
    ActionExecutionResult,
    ActionExecutor,
    WorkItem,
)


class ProviderActionExecutor(ActionExecutor):
    """Converts registered RecoveryOS actions into adapter calls."""

    _MESSAGE_ACTIONS = {
        "SEND_EMAIL": "email",
        "SEND_SMS": "sms",
        "SEND_WHATSAPP": "whatsapp",
        "SEND_PUSH": "push",
        "SHOW_IN_APP": "in_app",
    }

    def __init__(
        self,
        *,
        payment: PaymentProvider,
        messaging: MessagingProvider,
        merchant_id: str,
    ) -> None:
        if not merchant_id:
            raise ValueError("merchant_id is required")
        self.payment = payment
        self.messaging = messaging
        self.merchant_id = merchant_id

    def execute(self, work: WorkItem) -> ActionExecutionResult:
        try:
            if work.action_type == "GENERATE_PAYMENT_LINK":
                if (
                    work.obligation_id is None
                    or work.amount_minor_units is None
                    or work.currency is None
                ):
                    raise ActionExecutionError(
                        "missing_payment_context",
                        "payment link context is unavailable",
                        retryable=False,
                    )
                self._ensure_payment_outstanding(work)
                link_result = self.payment.create_retry_link(
                    PaymentLinkRequest(
                        merchant_id=self.merchant_id,
                        obligation_id=work.obligation_id,
                        amount_minor_units=work.amount_minor_units,
                        currency=work.currency,
                        idempotency_key=work.action_idempotency_key,
                    )
                )
                return ActionExecutionResult(provider_reference=link_result.provider_reference)
            channel = self._MESSAGE_ACTIONS.get(work.action_type)
            if channel is not None:
                if work.customer_external_id is None:
                    raise ActionExecutionError(
                        "missing_recipient",
                        "customer contact is unavailable",
                        retryable=False,
                    )
                self._ensure_payment_outstanding(work)
                message_result = self.messaging.send(
                    MessageRequest(
                        merchant_id=self.merchant_id,
                        channel=channel,
                        recipient_external_id=work.customer_external_id,
                        case_id=work.case_id,
                        idempotency_key=work.action_idempotency_key,
                        template_key="recovery_payment_prompt",
                    )
                )
                return ActionExecutionResult(
                    provider_reference=message_result.provider_reference,
                    cost_minor_units=message_result.cost_minor_units,
                )
            raise ActionExecutionError(
                "unsupported_action",
                "action is not supported by the configured provider executor",
                retryable=False,
            )
        except ActionExecutionError:
            raise
        except ProviderError as exc:
            raise ActionExecutionError(
                exc.category, exc.safe_message, retryable=exc.retryable
            ) from exc

    def _ensure_payment_outstanding(self, work: WorkItem) -> None:
        """Perform an adapter-level check immediately before an external effect."""
        if work.payment_id is None:
            return
        try:
            snapshot = self.payment.get_payment_status(self.merchant_id, work.payment_id)
        except ProviderError as exc:
            raise ActionExecutionError(
                exc.category,
                exc.safe_message,
                retryable=exc.retryable,
            ) from exc
        if snapshot.status == PaymentStatus.FAILED:
            return
        if snapshot.status in {
            PaymentStatus.SUCCEEDED,
            PaymentStatus.REFUNDED,
            PaymentStatus.REVERSED,
        }:
            raise ActionExecutionError(
                "payment_verified",
                "payment is no longer outstanding",
                retryable=False,
            )
        raise ActionExecutionError(
            "payment_status_unavailable",
            "payment status is not final",
            retryable=True,
        )
