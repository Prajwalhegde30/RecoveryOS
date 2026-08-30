from __future__ import annotations

import argparse
import json

from app.config import get_settings
from app.persistence.base import build_engine, build_session_factory
from app.scoring.economics import ScoringConfig
from app.simulator.service import SimulatorConfig, SimulatorService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deterministic RecoveryOS simulator batch")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--transactions", type=int, required=True)
    parser.add_argument("--merchant-id", action="append", required=True)
    parser.add_argument("--amount-minor-units", type=int, action="append", required=True)
    parser.add_argument("--payment-method", action="append", required=True)
    parser.add_argument("--failure-code", action="append", required=True)
    args = parser.parse_args()
    settings = get_settings()
    factory = build_session_factory(build_engine(settings.database_url))
    with factory() as session:
        result = SimulatorService(
            session,
            SimulatorConfig(
                seed=args.seed,
                merchant_ids=tuple(args.merchant_id),
                transaction_count=args.transactions,
                amounts_minor_units=tuple(args.amount_minor_units),
                payment_methods=tuple(args.payment_method),
                failure_codes=tuple(args.failure_code),
                max_recovery_attempts=settings.max_recovery_attempts,
                scoring_config=ScoringConfig(
                    settings.scoring_base_probability_percent,
                    settings.scoring_timeout_adjustment_percent,
                    settings.scoring_incident_penalty_percent,
                    settings.scoring_confidence_weight_percent,
                    settings.scoring_version,
                ),
            ),
        ).run()
        print(json.dumps(result.__dict__, sort_keys=True))


if __name__ == "__main__":
    main()
