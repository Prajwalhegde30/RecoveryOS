from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringConfig:
    base_probability_percent: int
    temporary_timeout_adjustment_percent: int
    incident_penalty_percent: int
    priority_confidence_weight_percent: int
    version: str


@dataclass(frozen=True)
class ScoreResult:
    probability_percent: int
    expected_recoverable_amount: int
    priority_score: int
    inputs: dict[str, int | str | bool]
    version: str


def calculate_score(
    amount_minor_units: int,
    diagnosis_category: str,
    diagnosis_confidence_percent: int,
    *,
    incident_active: bool,
    config: ScoringConfig,
) -> ScoreResult:
    if amount_minor_units < 0:
        raise ValueError("amount_minor_units must be non-negative")
    probability = config.base_probability_percent
    if diagnosis_category == "temporary_payment_failure" and not incident_active:
        probability += config.temporary_timeout_adjustment_percent
    if incident_active:
        probability -= config.incident_penalty_percent
    probability = min(max(probability, 0), 100)
    confidence = min(max(diagnosis_confidence_percent, 0), 100)
    expected = amount_minor_units * probability // 100
    confidence_weight = config.priority_confidence_weight_percent
    confidence_factor = (100 - confidence_weight) + (confidence * confidence_weight // 100)
    priority = expected * confidence_factor // 100
    return ScoreResult(
        probability_percent=probability,
        expected_recoverable_amount=expected,
        priority_score=priority,
        inputs={
            "amount_minor_units": amount_minor_units,
            "base_probability_percent": config.base_probability_percent,
            "diagnosis_confidence_percent": confidence,
            "incident_active": incident_active,
        },
        version=config.version,
    )
