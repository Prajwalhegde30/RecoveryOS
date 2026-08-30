from app.ai.contracts import ActionType, RecommendationEvidence, RecommendationOutput


def deterministic_fallback(evidence: RecommendationEvidence) -> RecommendationOutput:
    """Return a safe registered proposal when AI is unavailable or uncertain."""

    action_by_cause = {
        "temporary_payment_failure": ActionType.WAIT,
        "issuing_bank_issue": ActionType.WAIT,
        "insufficient_funds": ActionType.SCHEDULE_RETRY,
        "expired_card": ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
        "authentication_failure": ActionType.WAIT,
        "mandate_failure": ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
        "customer_cancellation": ActionType.STOP,
        "checkout_abandonment": ActionType.GENERATE_PAYMENT_LINK,
        "systemic_payment_degradation": ActionType.WAIT,
        "invalid_payment_instrument": ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
        "merchant_configuration_problem": ActionType.ESCALATE_TO_HUMAN,
        "unknown": ActionType.ESCALATE_TO_HUMAN,
    }
    action = action_by_cause.get(evidence.root_cause, ActionType.ESCALATE_TO_HUMAN)
    return RecommendationOutput(
        action=action,
        parameters={},
        reason_code=f"FALLBACK_{evidence.root_cause.upper()}",
        rationale=(
            "Deterministic fallback selected from the classified root cause and available "
            "case evidence; policy must authorize it before execution."
        ),
        evidence=[
            f"root_cause:{evidence.root_cause}",
            f"root_cause_confidence_percent:{evidence.root_cause_confidence_percent}",
            f"scoring_version:{evidence.scoring_version}",
        ],
        confidence_percent=evidence.root_cause_confidence_percent,
        fallback_action=ActionType.ESCALATE_TO_HUMAN,
        prompt_version="not_applicable",
        model_version="deterministic-fallback-v1",
        schema_version="recommendation-v1",
    )
