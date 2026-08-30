from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from app.persistence.models import RecoveryCaseStatus


class TransitionError(ValueError):
    """Raised when a Recovery Case transition is not in the product matrix."""


class ActorType(StrEnum):
    SYSTEM = "system"
    OPERATOR = "operator"
    ADMIN = "admin"
    WORKER = "worker"


TERMINAL_STATES = frozenset(
    {
        RecoveryCaseStatus.RECOVERED,
        RecoveryCaseStatus.OPTED_OUT,
        RecoveryCaseStatus.CANCELLED,
        RecoveryCaseStatus.EXHAUSTED,
    }
)

_OPEN_STATES = frozenset(RecoveryCaseStatus) - TERMINAL_STATES

TRANSITIONS: Mapping[RecoveryCaseStatus, frozenset[RecoveryCaseStatus]] = {
    RecoveryCaseStatus.DETECTED: frozenset(
        {
            RecoveryCaseStatus.ANALYZING,
            RecoveryCaseStatus.RECOVERED,
            RecoveryCaseStatus.OPTED_OUT,
            RecoveryCaseStatus.CANCELLED,
            RecoveryCaseStatus.SUPPRESSED,
            RecoveryCaseStatus.EXHAUSTED,
        }
    ),
    RecoveryCaseStatus.ANALYZING: frozenset(
        {
            RecoveryCaseStatus.ACTION_PENDING,
            RecoveryCaseStatus.RECOVERED,
            RecoveryCaseStatus.OPTED_OUT,
            RecoveryCaseStatus.CANCELLED,
            RecoveryCaseStatus.SUPPRESSED,
            RecoveryCaseStatus.EXHAUSTED,
        }
    ),
    RecoveryCaseStatus.ACTION_PENDING: frozenset(
        {
            RecoveryCaseStatus.POLICY_CHECK,
            RecoveryCaseStatus.RECOVERED,
            RecoveryCaseStatus.OPTED_OUT,
            RecoveryCaseStatus.CANCELLED,
            RecoveryCaseStatus.SUPPRESSED,
            RecoveryCaseStatus.EXHAUSTED,
        }
    ),
    RecoveryCaseStatus.POLICY_CHECK: frozenset(
        {
            RecoveryCaseStatus.SCHEDULED,
            RecoveryCaseStatus.ACTION_EXECUTED,
            RecoveryCaseStatus.ESCALATED,
            RecoveryCaseStatus.WAITING,
            RecoveryCaseStatus.SUPPRESSED,
            RecoveryCaseStatus.RECOVERED,
            RecoveryCaseStatus.OPTED_OUT,
            RecoveryCaseStatus.CANCELLED,
            RecoveryCaseStatus.EXHAUSTED,
        }
    ),
    RecoveryCaseStatus.SCHEDULED: frozenset(
        {
            RecoveryCaseStatus.ACTION_EXECUTED,
            RecoveryCaseStatus.RECOVERED,
            RecoveryCaseStatus.OPTED_OUT,
            RecoveryCaseStatus.CANCELLED,
            RecoveryCaseStatus.SUPPRESSED,
            RecoveryCaseStatus.EXHAUSTED,
        }
    ),
    RecoveryCaseStatus.ACTION_EXECUTED: frozenset(
        {
            RecoveryCaseStatus.WAITING,
            RecoveryCaseStatus.RECOVERED,
            RecoveryCaseStatus.ESCALATED,
            RecoveryCaseStatus.OPTED_OUT,
            RecoveryCaseStatus.CANCELLED,
            RecoveryCaseStatus.EXHAUSTED,
        }
    ),
    RecoveryCaseStatus.WAITING: frozenset(
        {
            RecoveryCaseStatus.RECOVERED,
            RecoveryCaseStatus.OPTED_OUT,
            RecoveryCaseStatus.CANCELLED,
            RecoveryCaseStatus.SUPPRESSED,
            RecoveryCaseStatus.EXHAUSTED,
            RecoveryCaseStatus.ACTION_PENDING,
        }
    ),
    RecoveryCaseStatus.ESCALATED: frozenset(
        {
            RecoveryCaseStatus.RECOVERED,
            RecoveryCaseStatus.OPTED_OUT,
            RecoveryCaseStatus.CANCELLED,
            RecoveryCaseStatus.ACTION_PENDING,
            RecoveryCaseStatus.EXHAUSTED,
        }
    ),
    RecoveryCaseStatus.SUPPRESSED: frozenset(
        {
            RecoveryCaseStatus.WAITING,
            RecoveryCaseStatus.ACTION_PENDING,
            RecoveryCaseStatus.RECOVERED,
            RecoveryCaseStatus.OPTED_OUT,
            RecoveryCaseStatus.CANCELLED,
            RecoveryCaseStatus.EXHAUSTED,
        }
    ),
    RecoveryCaseStatus.RECOVERED: frozenset(),
    RecoveryCaseStatus.OPTED_OUT: frozenset(),
    RecoveryCaseStatus.CANCELLED: frozenset(),
    RecoveryCaseStatus.EXHAUSTED: frozenset(),
}


def can_transition(current: RecoveryCaseStatus, target: RecoveryCaseStatus) -> bool:
    return target in TRANSITIONS.get(current, frozenset())


def validate_transition(current: RecoveryCaseStatus, target: RecoveryCaseStatus) -> None:
    if current in TERMINAL_STATES:
        raise TransitionError(f"terminal case cannot transition from {current} to {target}")
    if not can_transition(current, target):
        raise TransitionError(f"illegal case transition from {current} to {target}")


def is_open(state: RecoveryCaseStatus) -> bool:
    return state in _OPEN_STATES
