from datetime import time
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.contracts import ActionType


class PolicyVersionStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"


class Channel(StrEnum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


class MerchantPolicyDocument(BaseModel):
    """Versioned merchant business rules; no field has an implicit unlimited value."""

    model_config = ConfigDict(extra="forbid")

    timezone: str = Field(min_length=1, max_length=64)
    max_attempts: int = Field(ge=1)
    min_contact_interval_minutes: int = Field(ge=0)
    quiet_hours_start: time
    quiet_hours_end: time
    approval_threshold_minor_units: int = Field(ge=0)
    max_contacts_per_case: int = Field(ge=0)
    max_contacts_per_customer: int = Field(ge=0)
    sequence_duration_minutes: int = Field(ge=0)
    enabled_channels: set[Channel] = Field(min_length=1)
    retry_max_attempts: int = Field(ge=0)
    incident_suppression_enabled: bool
    fallback_action: ActionType

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be an installed IANA timezone") from exc
        return value


def policy_json(policy: MerchantPolicyDocument) -> dict[str, object]:
    """Serialize the typed document into the JSON shape persisted by policy versions."""

    return policy.model_dump(mode="json")


def policy_from_json(value: dict[str, object]) -> MerchantPolicyDocument:
    """Validate persisted JSON before it is used by an application service."""

    return MerchantPolicyDocument.model_validate(value)
