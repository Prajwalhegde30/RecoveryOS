from datetime import UTC
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.events.contracts import EventIngestionResult, RevenueEvent
from app.persistence.models import AuditEvent, ProcessedEvent
from app.persistence.models import RevenueEvent as RevenueEventRecord


def _utc_naive(value):
    return value.astimezone(UTC).replace(tzinfo=None)


class EventIngestionService:
    def __init__(self, session: Session, provider: str) -> None:
        self.session = session
        self.provider = provider

    def ingest(self, event: RevenueEvent) -> EventIngestionResult:
        correlation_id = event.correlation_id or str(uuid4())
        try:
            with self.session.begin():
                processed = ProcessedEvent(
                    merchant_id=event.merchant_id,
                    provider=self.provider,
                    idempotency_key=event.event_id,
                    event_type=event.event_type,
                    result="accepted",
                    correlation_id=correlation_id,
                )
                self.session.add(processed)
                self.session.flush()
                self.session.add(
                    RevenueEventRecord(
                        merchant_id=event.merchant_id,
                        provider=self.provider,
                        external_event_id=event.event_id,
                        event_type=event.event_type,
                        source_object_id=event.source_object_id,
                        normalized_payload=event.model_dump(mode="json"),
                        provider_event_at=_utc_naive(event.occurred_at),
                        processing_status="RECEIVED",
                        correlation_id=correlation_id,
                    )
                )
        except IntegrityError:
            self.session.rollback()
            existing = self.session.scalar(
                select(ProcessedEvent).where(
                    ProcessedEvent.merchant_id == event.merchant_id,
                    ProcessedEvent.provider == self.provider,
                    ProcessedEvent.idempotency_key == event.event_id,
                )
            )
            if existing is None:
                raise
            existing_correlation_id = existing.correlation_id
            existing_result = existing.result
            self.session.rollback()
            with self.session.begin():
                self.session.add(
                    AuditEvent(
                        merchant_id=event.merchant_id,
                        entity_type="revenue_event",
                        entity_id=existing.id,
                        event_type="EVENT_DUPLICATE_RECEIVED",
                        actor_type="system",
                        reason="duplicate external event ignored by idempotency boundary",
                        metadata_safe_json={"provider": self.provider},
                        correlation_id=existing_correlation_id,
                    )
                )
            return EventIngestionResult(
                event_id=event.event_id,
                status=existing_result,
                duplicate=True,
                correlation_id=existing_correlation_id,
            )
        return EventIngestionResult(
            event_id=event.event_id,
            status="accepted",
            duplicate=False,
            correlation_id=correlation_id,
        )

    def replay(self, merchant_id: str, event_id: str) -> EventIngestionResult:
        """Replay through the normal identity path without creating a new event identity."""
        record = self.session.scalar(
            select(RevenueEventRecord).where(
                RevenueEventRecord.merchant_id == merchant_id,
                RevenueEventRecord.provider == self.provider,
                RevenueEventRecord.external_event_id == event_id,
            )
        )
        if record is None:
            raise LookupError("event not found")
        processed = self.session.scalar(
            select(ProcessedEvent).where(
                ProcessedEvent.merchant_id == merchant_id,
                ProcessedEvent.provider == self.provider,
                ProcessedEvent.idempotency_key == event_id,
            )
        )
        if processed is None:
            raise LookupError("processed event not found")
        payload = RevenueEvent.model_validate(record.normalized_payload)
        was_failed = processed.result == "failed"
        correlation_id = processed.correlation_id
        self.session.rollback()
        if was_failed:
            with self.session.begin():
                self.session.execute(
                    select(ProcessedEvent)
                    .where(ProcessedEvent.id == processed.id)
                    .with_for_update()
                ).scalar_one().result = "accepted"
                self.session.execute(
                    select(RevenueEventRecord)
                    .where(RevenueEventRecord.id == record.id)
                    .with_for_update()
                ).scalar_one().processing_status = "RECEIVED"
            return EventIngestionResult(
                event_id=event_id,
                status="accepted",
                duplicate=False,
                correlation_id=correlation_id,
            )
        return self.ingest(payload)

    def mark_processing_failed(self, merchant_id: str, event_id: str) -> None:
        with self.session.begin():
            processed = self.session.scalar(
                select(ProcessedEvent).where(
                    ProcessedEvent.merchant_id == merchant_id,
                    ProcessedEvent.provider == self.provider,
                    ProcessedEvent.idempotency_key == event_id,
                )
            )
            record = self.session.scalar(
                select(RevenueEventRecord).where(
                    RevenueEventRecord.merchant_id == merchant_id,
                    RevenueEventRecord.provider == self.provider,
                    RevenueEventRecord.external_event_id == event_id,
                )
            )
            if processed is None or record is None:
                raise LookupError("event not found")
            processed.result = "failed"
            record.processing_status = "FAILED"
