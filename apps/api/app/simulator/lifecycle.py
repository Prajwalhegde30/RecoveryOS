from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cases.state_machine import ActorType
from app.persistence.models import AuditEvent, SimulatorRun
from app.simulator.service import SimulatorConfig, SimulatorRunResult, SimulatorService


class SimulatorRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RESET = "RESET"


@dataclass(frozen=True)
class SimulatorLifecycleResult:
    run_id: str
    status: SimulatorRunStatus
    result: SimulatorRunResult | None
    error_safe: str | None = None


class SimulatorLifecycleService:
    """Persists simulator lifecycle while preserving all generated domain facts."""

    def __init__(self, session: Session, merchant_id: str) -> None:
        if not merchant_id:
            raise ValueError("merchant_id is required")
        self.session = session
        self.merchant_id = merchant_id

    def start(
        self,
        config: SimulatorConfig,
        *,
        run_key: str,
        actor_id: str,
        correlation_id: str = "simulator-run",
    ) -> SimulatorLifecycleResult:
        if not run_key or not actor_id:
            raise ValueError("run_key and actor_id are required")
        snapshot = _config_snapshot(config)
        self.session.rollback()
        with self.session.begin():
            run = self.session.scalar(
                select(SimulatorRun)
                .where(
                    SimulatorRun.merchant_id == self.merchant_id,
                    SimulatorRun.run_key == run_key,
                )
                .with_for_update()
            )
            if run is None:
                run = SimulatorRun(
                    merchant_id=self.merchant_id,
                    run_key=run_key,
                    seed=config.seed,
                    status=SimulatorRunStatus.PENDING,
                    label="synthetic_simulator_data",
                    configuration_json=snapshot,
                )
                self.session.add(run)
                self.session.flush()
                self._audit(run, "SIMULATOR_RUN_CREATED", actor_id, correlation_id)
            elif run.status == SimulatorRunStatus.COMPLETED and run.result_json is not None:
                return SimulatorLifecycleResult(
                    run.id,
                    SimulatorRunStatus.COMPLETED,
                    _result_from_json(run.result_json),
                )
            elif run.status == SimulatorRunStatus.RUNNING:
                return SimulatorLifecycleResult(run.id, SimulatorRunStatus.RUNNING, None)
            else:
                run.status = SimulatorRunStatus.PENDING
                run.configuration_json = snapshot
                run.result_json = None
                run.error_safe = None
                run.completed_at = None
        run_id = run.id
        self.session.rollback()
        try:
            with self.session.begin():
                run = self._locked(run_id)
                run.status = SimulatorRunStatus.RUNNING
                run.started_at = _utc_now()
                self._audit(run, "SIMULATOR_RUN_STARTED", actor_id, correlation_id)
            self.session.rollback()
            result = SimulatorService(self.session, config).run()
            result_json = _result_json(result)
            self.session.rollback()
            with self.session.begin():
                run = self._locked(run_id)
                run.status = SimulatorRunStatus.COMPLETED
                run.label = result.label
                run.result_json = result_json
                run.completed_at = _utc_now()
                self._audit(run, "SIMULATOR_RUN_COMPLETED", actor_id, correlation_id)
            return SimulatorLifecycleResult(run_id, SimulatorRunStatus.COMPLETED, result)
        except Exception:
            self.session.rollback()
            with self.session.begin():
                run = self._locked(run_id)
                run.status = SimulatorRunStatus.FAILED
                run.error_safe = "simulator execution failed; inspect the correlated audit event"
                run.completed_at = _utc_now()
                self._audit(run, "SIMULATOR_RUN_FAILED", actor_id, correlation_id)
            raise

    def get(self, run_id: str) -> SimulatorLifecycleResult:
        self.session.rollback()
        run = self.session.scalar(
            select(SimulatorRun).where(
                SimulatorRun.id == run_id,
                SimulatorRun.merchant_id == self.merchant_id,
            )
        )
        if run is None:
            raise LookupError("simulator run not found")
        return SimulatorLifecycleResult(
            run.id,
            SimulatorRunStatus(run.status),
            _result_from_json(run.result_json) if run.result_json else None,
            run.error_safe,
        )

    def reset(self, run_id: str, *, actor_id: str, correlation_id: str) -> SimulatorLifecycleResult:
        if not actor_id:
            raise ValueError("actor_id is required")
        self.session.rollback()
        with self.session.begin():
            run = self._locked(run_id)
            if run.status == SimulatorRunStatus.RUNNING:
                raise ValueError("running simulator run cannot be reset")
            run.status = SimulatorRunStatus.RESET
            run.result_json = None
            run.error_safe = None
            run.completed_at = _utc_now()
            self._audit(run, "SIMULATOR_RUN_RESET", actor_id, correlation_id)
            return SimulatorLifecycleResult(run.id, SimulatorRunStatus.RESET, None)

    def _locked(self, run_id: str) -> SimulatorRun:
        run = self.session.scalar(
            select(SimulatorRun)
            .where(SimulatorRun.id == run_id, SimulatorRun.merchant_id == self.merchant_id)
            .with_for_update()
        )
        if run is None:
            raise LookupError("simulator run not found")
        return run

    def _audit(
        self, run: SimulatorRun, event_type: str, actor_id: str, correlation_id: str
    ) -> None:
        self.session.add(
            AuditEvent(
                merchant_id=self.merchant_id,
                entity_type="simulator_run",
                entity_id=run.id,
                event_type=event_type,
                actor_type=ActorType.ADMIN,
                actor_id=actor_id,
                reason=event_type.lower().replace("_", " "),
                metadata_safe_json={"run_key": run.run_key, "seed": run.seed},
                correlation_id=correlation_id,
            )
        )


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _config_snapshot(config: SimulatorConfig) -> dict[str, Any]:
    data = asdict(config)
    data["merchant_ids"] = list(config.merchant_ids)
    data["amounts_minor_units"] = list(config.amounts_minor_units)
    data["payment_methods"] = list(config.payment_methods)
    data["failure_codes"] = list(config.failure_codes)
    data["event_types"] = [event_type.value for event_type in config.event_types]
    for key in (
        "high_value_indices",
        "duplicate_event_indices",
        "opt_out_indices",
        "incident_indices",
        "natural_recovery_indices",
        "assisted_recovery_indices",
        "provider_failure_indices",
    ):
        data[key] = sorted(data[key])
    data["scoring_config"] = asdict(config.scoring_config)
    return data


def _result_json(result: SimulatorRunResult) -> dict[str, Any]:
    return asdict(result)


def _result_from_json(value: dict[str, Any]) -> SimulatorRunResult:
    return SimulatorRunResult(
        seed=int(value["seed"]),
        label=str(value["label"]),
        persisted_event_count=int(value["persisted_event_count"]),
        duplicate_event_count=int(value["duplicate_event_count"]),
        case_count=int(value["case_count"]),
        recommendation_count=int(value["recommendation_count"]),
        success_event_count=int(value["success_event_count"]),
        scenario_counts={str(k): int(v) for k, v in value["scenario_counts"].items()},
        event_ids=tuple(str(item) for item in value["event_ids"]),
        case_ids=tuple(str(item) for item in value["case_ids"]),
    )
