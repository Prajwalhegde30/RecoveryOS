from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models import WorkerHeartbeat


class WorkerHeartbeatService:
    """Persists a safe, tenant-scoped liveness signal for a running worker."""

    def __init__(self, session: Session, merchant_id: str, worker_id: str) -> None:
        if not merchant_id or not worker_id:
            raise ValueError("merchant_id and worker_id are required")
        self.session = session
        self.merchant_id = merchant_id
        self.worker_id = worker_id

    def beat(self, *, status: str = "healthy", detail_safe: str = "worker loop active") -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        self.session.rollback()
        with self.session.begin():
            heartbeat = self.session.scalar(
                select(WorkerHeartbeat)
                .where(
                    WorkerHeartbeat.merchant_id == self.merchant_id,
                    WorkerHeartbeat.worker_id == self.worker_id,
                )
                .with_for_update()
            )
            if heartbeat is None:
                heartbeat = WorkerHeartbeat(
                    merchant_id=self.merchant_id,
                    worker_id=self.worker_id,
                    status=status,
                    last_seen_at=now,
                    detail_safe=detail_safe[:255],
                )
                self.session.add(heartbeat)
            else:
                heartbeat.status = status
                heartbeat.last_seen_at = now
                heartbeat.detail_safe = detail_safe[:255]

