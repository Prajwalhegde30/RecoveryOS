from dataclasses import dataclass

from app.events.contracts import RevenueEvent, RevenueEventType


@dataclass(frozen=True)
class ObligationIdentity:
    obligation_type: str
    external_id: str


RECOVERABLE_EVENT_TYPES = frozenset(
    {
        RevenueEventType.PAYMENT_FAILED,
        RevenueEventType.CHECKOUT_ABANDONED,
        RevenueEventType.SUBSCRIPTION_PAYMENT_FAILED,
        RevenueEventType.INVOICE_OVERDUE,
    }
)


def obligation_identity(event: RevenueEvent) -> ObligationIdentity | None:
    if event.event_type not in RECOVERABLE_EVENT_TYPES:
        return None
    obligation_type = event.obligation_type
    if obligation_type is None:
        obligation_type = {
            RevenueEventType.PAYMENT_FAILED: "payment",
            RevenueEventType.CHECKOUT_ABANDONED: "checkout",
            RevenueEventType.SUBSCRIPTION_PAYMENT_FAILED: "subscription",
            RevenueEventType.INVOICE_OVERDUE: "invoice",
        }[event.event_type]
    external_id = event.external_obligation_id or event.source_object_id
    return ObligationIdentity(obligation_type=obligation_type, external_id=external_id)
