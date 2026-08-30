from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ai.contracts import ActionType
from app.persistence.models import RecoveryCaseStatus
from app.policy.schema import Channel, MerchantPolicyDocument


class PolicyResult:
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    SCHEDULE = "SCHEDULE"
    SUPPRESS = "SUPPRESS"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    STOP = "STOP"


@dataclass(frozen=True)
class PolicyEvaluationContext:
    action_type: ActionType
    case_status: RecoveryCaseStatus
    amount_at_risk_minor_units: int
    payment_verified: bool = False
    customer_opted_out: bool = False
    stale_or_invalid: bool = False
    incident_active: bool = False
    case_contact_count: int = 0
    customer_contact_count: int = 0
    last_contact_at: datetime | None = None
    now: datetime | None = None
    channel: Channel | None = None

    def __post_init__(self) -> None:
        if self.amount_at_risk_minor_units < 0:
            raise ValueError("amount_at_risk_minor_units must be non-negative")
        if self.case_contact_count < 0 or self.customer_contact_count < 0:
            raise ValueError("contact counts must be non-negative")


@dataclass(frozen=True)
class PolicyEvaluation:
    result: str
    decisive_rule: str
    reason: str
    fallback_action: ActionType | None = None


_TERMINAL_STATES = frozenset(
    {
        RecoveryCaseStatus.RECOVERED,
        RecoveryCaseStatus.OPTED_OUT,
        RecoveryCaseStatus.CANCELLED,
        RecoveryCaseStatus.EXHAUSTED,
    }
)

_ACTION_CHANNELS = {
    ActionType.SEND_EMAIL: Channel.EMAIL,
    ActionType.SEND_SMS: Channel.SMS,
    ActionType.SEND_WHATSAPP: Channel.WHATSAPP,
}


def evaluate_policy(
    policy: MerchantPolicyDocument, context: PolicyEvaluationContext
) -> PolicyEvaluation:
    """Apply PRD precedence and return the first decisive result."""

    if context.payment_verified:
        return PolicyEvaluation(PolicyResult.STOP, "PAYMENT_VERIFIED", "payment is authoritative")
    if context.customer_opted_out:
        return PolicyEvaluation(PolicyResult.STOP, "CUSTOMER_OPTED_OUT", "customer opted out")
    if context.case_status in _TERMINAL_STATES:
        return PolicyEvaluation(PolicyResult.STOP, "TERMINAL_CASE", "case is terminal")
    if context.stale_or_invalid:
        return PolicyEvaluation(
            PolicyResult.STOP, "STALE_OR_INVALID", "case context is stale or invalid"
        )
    if context.incident_active:
        if policy.incident_suppression_enabled:
            return PolicyEvaluation(
                PolicyResult.SUPPRESS,
                "INCIDENT_SUPPRESSION",
                "active systemic incident suppresses customer outreach",
            )
        return PolicyEvaluation(
            PolicyResult.SCHEDULE,
            "INCIDENT_WAIT",
            "active systemic incident delays customer outreach",
        )
    if (
        context.case_contact_count >= policy.max_contacts_per_case
        or context.customer_contact_count >= policy.max_contacts_per_customer
    ):
        return PolicyEvaluation(
            PolicyResult.BLOCK, "CONTACT_LIMIT", "configured contact limit reached"
        )
    if context.last_contact_at is not None:
        now = _required_now(context)
        elapsed_seconds = (now - context.last_contact_at).total_seconds()
        if elapsed_seconds < policy.min_contact_interval_minutes * 60:
            return PolicyEvaluation(
                PolicyResult.SCHEDULE,
                "MINIMUM_CONTACT_INTERVAL",
                "minimum contact interval has not elapsed",
            )
    if _is_quiet_hours(policy, _required_now(context)):
        return PolicyEvaluation(
            PolicyResult.SCHEDULE, "QUIET_HOURS", "merchant quiet hours are active"
        )
    if context.amount_at_risk_minor_units >= policy.approval_threshold_minor_units:
        return PolicyEvaluation(
            PolicyResult.REQUIRE_APPROVAL,
            "APPROVAL_THRESHOLD",
            "amount meets the configured approval threshold",
        )
    expected_channel = _ACTION_CHANNELS.get(context.action_type)
    if expected_channel is not None and expected_channel not in policy.enabled_channels:
        return PolicyEvaluation(
            PolicyResult.BLOCK,
            "CHANNEL_UNAVAILABLE",
            "recommended channel is not enabled by merchant policy",
            fallback_action=policy.fallback_action,
        )
    return PolicyEvaluation(
        PolicyResult.ALLOW, "NORMAL_POLICY", "all configured policy checks passed"
    )


def _required_now(context: PolicyEvaluationContext) -> datetime:
    if context.now is None or context.now.tzinfo is None:
        raise ValueError("policy evaluation requires a timezone-aware now")
    return context.now


def _is_quiet_hours(policy: MerchantPolicyDocument, now: datetime) -> bool:
    local_time = now.astimezone(ZoneInfo(policy.timezone)).time()
    start = policy.quiet_hours_start
    end = policy.quiet_hours_end
    if start < end:
        return start <= local_time < end
    return local_time >= start or local_time < end
