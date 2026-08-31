from __future__ import annotations

import argparse
from threading import Event

from app.config import get_settings
from app.integrations.executor import ProviderActionExecutor
from app.integrations.simulated import SimulatedMessagingProvider, SimulatedPaymentProvider
from app.jobs.service import JobConfig, JobService
from app.persistence.base import build_engine, build_session_factory
from app.workers.service import ProviderPreflightChecker, WorkerService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RecoveryOS durable action worker")
    parser.add_argument("--merchant-id", required=True)
    parser.add_argument("--worker-id", default="worker")
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    args = parser.parse_args()
    settings = get_settings()
    factory = build_session_factory(build_engine(settings.database_url))
    payment = SimulatedPaymentProvider()
    messaging = SimulatedMessagingProvider()
    with factory() as session:
        jobs = JobService(
            session,
            args.merchant_id,
            JobConfig(
                max_attempts=settings.max_recovery_attempts,
                lease_seconds=settings.job_lease_seconds,
                backoff_base_seconds=settings.job_backoff_base_seconds,
                backoff_max_seconds=settings.job_backoff_max_seconds,
            ),
        )
        worker = WorkerService(
            session,
            args.merchant_id,
            jobs,
            ProviderActionExecutor(
                payment=payment,
                messaging=messaging,
                merchant_id=args.merchant_id,
            ),
            ProviderPreflightChecker(session, args.merchant_id, payment),
            worker_id=args.worker_id,
        )
        worker.run(Event(), poll_interval_seconds=args.poll_interval_seconds)


if __name__ == "__main__":
    main()
