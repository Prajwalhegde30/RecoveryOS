from dataclasses import dataclass

from app.events.contracts import RevenueEventType


class RootCause:
    TEMPORARY_PAYMENT_FAILURE = "temporary_payment_failure"
    ISSUING_BANK_ISSUE = "issuing_bank_issue"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    EXPIRED_CARD = "expired_card"
    AUTHENTICATION_FAILURE = "authentication_failure"
    MANDATE_FAILURE = "mandate_failure"
    CUSTOMER_CANCELLATION = "customer_cancellation"
    CHECKOUT_ABANDONMENT = "checkout_abandonment"
    SYSTEMIC_DEGRADATION = "systemic_payment_degradation"
    INVALID_PAYMENT_INSTRUMENT = "invalid_payment_instrument"
    MERCHANT_CONFIGURATION = "merchant_configuration_problem"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Diagnosis:
    category: str
    confidence_percent: int
    evidence: tuple[str, ...]
    version: str


def classify(
    event_type: str,
    failure_code: str | None,
    *,
    incident_active: bool = False,
) -> Diagnosis:
    if incident_active:
        return Diagnosis(RootCause.SYSTEMIC_DEGRADATION, 90, ("active_incident",), "diagnosis-v1")
    if event_type in {
        RevenueEventType.CHECKOUT_ABANDONED,
        RevenueEventType.INVOICE_OVERDUE,
    }:
        category = (
            RootCause.CHECKOUT_ABANDONMENT
            if event_type == RevenueEventType.CHECKOUT_ABANDONED
            else RootCause.UNKNOWN
        )
        return Diagnosis(category, 90, (event_type,), "diagnosis-v1")

    normalized = (failure_code or "").upper()
    mapping = {
        "UPI_TIMEOUT": RootCause.TEMPORARY_PAYMENT_FAILURE,
        "NETWORK_TIMEOUT": RootCause.TEMPORARY_PAYMENT_FAILURE,
        "BANK_UNAVAILABLE": RootCause.ISSUING_BANK_ISSUE,
        "INSUFFICIENT_FUNDS": RootCause.INSUFFICIENT_FUNDS,
        "CARD_EXPIRED": RootCause.EXPIRED_CARD,
        "OTP_FAILED": RootCause.AUTHENTICATION_FAILURE,
        "AUTHENTICATION_FAILED": RootCause.AUTHENTICATION_FAILURE,
        "MANDATE_FAILED": RootCause.MANDATE_FAILURE,
        "CUSTOMER_CANCELLED": RootCause.CUSTOMER_CANCELLATION,
        "INVALID_CARD": RootCause.INVALID_PAYMENT_INSTRUMENT,
        "INVALID_PAYMENT_INSTRUMENT": RootCause.INVALID_PAYMENT_INSTRUMENT,
        "MERCHANT_CONFIG_ERROR": RootCause.MERCHANT_CONFIGURATION,
    }
    category = mapping.get(normalized, RootCause.UNKNOWN)
    confidence = 85 if category != RootCause.UNKNOWN else 30
    evidence = (f"failure_code:{normalized}",) if normalized else ("failure_code_missing",)
    return Diagnosis(category, confidence, evidence, "diagnosis-v1")
