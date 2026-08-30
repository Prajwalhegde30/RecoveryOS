from datetime import UTC, datetime

import pytest

from app.ai.contracts import ActionType
from app.persistence.models import RecoveryCaseStatus
from app.policy.evaluator import PolicyEvaluationContext, PolicyResult, evaluate_policy
from app.policy.schema import Channel, MerchantPolicyDocument


def policy(**overrides: object) -> MerchantPolicyDocument:
    value: dict[str, object] = {
        "timezone": "Asia/Kolkata",
        "max_attempts": 3,
        "min_contact_interval_minutes": 240,
        "quiet_hours_start": "21:00",
        "quiet_hours_end": "08:00",
        "approval_threshold_minor_units": 5_000_000,
        "max_contacts_per_case": 3,
        "max_contacts_per_customer": 5,
        "sequence_duration_minutes": 1_440,
        "enabled_channels": {Channel.EMAIL, Channel.SMS},
        "retry_max_attempts": 3,
        "incident_suppression_enabled": True,
        "fallback_action": ActionType.WAIT,
    }
    value.update(overrides)
    return MerchantPolicyDocument(**value)


def context(**overrides: object) -> PolicyEvaluationContext:
    value: dict[str, object] = {
        "action_type": ActionType.SEND_EMAIL,
        "case_status": RecoveryCaseStatus.ACTION_PENDING,
        "amount_at_risk_minor_units": 10_000,
        "now": datetime(2026, 1, 1, 12, tzinfo=UTC),
    }
    value.update(overrides)
    return PolicyEvaluationContext(**value)


@pytest.mark.parametrize(
    ("overrides", "result", "rule"),
    (
        (
            {"payment_verified": True, "customer_opted_out": True},
            PolicyResult.STOP,
            "PAYMENT_VERIFIED",
        ),
        ({"customer_opted_out": True}, PolicyResult.STOP, "CUSTOMER_OPTED_OUT"),
        ({"case_status": RecoveryCaseStatus.RECOVERED}, PolicyResult.STOP, "TERMINAL_CASE"),
        ({"stale_or_invalid": True}, PolicyResult.STOP, "STALE_OR_INVALID"),
        ({"incident_active": True}, PolicyResult.SUPPRESS, "INCIDENT_SUPPRESSION"),
        ({"case_contact_count": 3}, PolicyResult.BLOCK, "CONTACT_LIMIT"),
        (
            {"last_contact_at": datetime(2026, 1, 1, 11, tzinfo=UTC)},
            PolicyResult.SCHEDULE,
            "MINIMUM_CONTACT_INTERVAL",
        ),
        ({"now": datetime(2026, 1, 1, 16, tzinfo=UTC)}, PolicyResult.SCHEDULE, "QUIET_HOURS"),
        (
            {"amount_at_risk_minor_units": 5_000_000},
            PolicyResult.REQUIRE_APPROVAL,
            "APPROVAL_THRESHOLD",
        ),
        ({"action_type": ActionType.SEND_WHATSAPP}, PolicyResult.BLOCK, "CHANNEL_UNAVAILABLE"),
        ({}, PolicyResult.ALLOW, "NORMAL_POLICY"),
    ),
)
def test_policy_precedence_returns_first_decisive_rule(
    overrides: dict[str, object], result: str, rule: str
) -> None:
    evaluation = evaluate_policy(policy(), context(**overrides))
    assert evaluation.result == result
    assert evaluation.decisive_rule == rule


def test_incident_without_suppression_delays_instead_of_contacting() -> None:
    evaluation = evaluate_policy(
        policy(incident_suppression_enabled=False), context(incident_active=True)
    )
    assert evaluation.result == PolicyResult.SCHEDULE
    assert evaluation.decisive_rule == "INCIDENT_WAIT"


def test_quiet_hours_supports_overnight_window_and_requires_timezone() -> None:
    assert (
        evaluate_policy(policy(), context(now=datetime(2026, 1, 1, 1, tzinfo=UTC))).decisive_rule
        == "QUIET_HOURS"
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_policy(policy(), context(now=datetime(2026, 1, 1, 12)))


def test_contact_counts_and_amount_cannot_be_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        context(amount_at_risk_minor_units=-1)
    with pytest.raises(ValueError, match="non-negative"):
        context(customer_contact_count=-1)
