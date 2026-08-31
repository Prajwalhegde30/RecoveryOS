import logging

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.ai.service import AIRecommendationService
from app.api.dependencies import get_db_session, get_session_factory
from app.api.routes import router as recovery_router
from app.cases.service import RecoveryCaseService
from app.cases.state_machine import is_open
from app.config import get_settings
from app.customers.service import CustomerOptOutService
from app.events.contracts import EventIngestionResult, RevenueEvent, RevenueEventType
from app.events.security import verify_signature
from app.events.service import EventIngestionService
from app.integrations.contracts import PaymentStatus
from app.integrations.simulated import SimulatedPaymentProvider
from app.observability.middleware import CorrelationRateLimitMiddleware
from app.persistence.models import RecoveryCaseStatus
from app.reconciliation.service import PaymentReconciliationService
from app.scoring.economics import ScoringConfig
from app.scoring.service import CaseAnalysisService

settings = get_settings()
app = FastAPI(title="RecoveryOS API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-Id", "X-Webhook-Signature"],
    expose_headers=["X-Correlation-Id"],
)
app.add_middleware(CorrelationRateLimitMiddleware)
app.include_router(recovery_router)
db_session_dependency = Depends(get_db_session)
_simulated_payment_provider = SimulatedPaymentProvider()


@app.exception_handler(Exception)
async def safe_unhandled_exception(request: Request, _: Exception) -> Response:
    """Return a safe correlated response without exposing internal details."""
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    # Keep the application log safe as well as the client response. Raw
    # exception text and tracebacks can contain provider payloads or secrets.
    logging.getLogger("recoveryos.request").error(
        "unhandled_request_error",
        extra={
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "error_type": "unhandled_exception",
        },
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "RecoveryOS could not complete the request",
            "retryable": True,
            "correlation_id": correlation_id,
        },
    )


@app.get("/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def readiness() -> dict[str, str]:
    try:
        with get_session_factory()() as session:
            session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logging.getLogger("recoveryos.health").warning(
            "readiness_dependency_unavailable",
            extra={"dependency": "database", "environment": settings.app_env},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database readiness check failed",
        ) from None
    return {"status": "ok", "environment": settings.app_env}


@app.post("/webhooks/{provider}", response_model=EventIngestionResult, tags=["events"])
async def receive_webhook(
    provider: str,
    request: Request,
    signature: str | None = Header(default=None, alias="X-Webhook-Signature"),
    session: Session = db_session_dependency,
) -> EventIngestionResult:
    payload = await request.body()
    if not verify_signature(payload, signature, settings.webhook_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid webhook signature"
        )
    try:
        event = RevenueEvent.model_validate_json(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid event payload"
        ) from exc
    if event.merchant_id == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid event payload"
        )
    result = EventIngestionService(session, provider).ingest(event)
    if event.event_type == RevenueEventType.CUSTOMER_OPTED_OUT and not result.duplicate:
        CustomerOptOutService(session, event.merchant_id, provider).apply(event)
        return result
    case = RecoveryCaseService(session, provider, settings.max_recovery_attempts).associate(event)
    if (
        provider == "simulator"
        and not result.duplicate
        and event.event_type
        in {
            RevenueEventType.PAYMENT_SUCCEEDED,
            RevenueEventType.INVOICE_PAID,
            RevenueEventType.PAYMENT_REFUNDED,
            RevenueEventType.PAYMENT_REVERSED,
        }
    ):
        _prepare_simulated_reconciliation(event)
        PaymentReconciliationService(
            session,
            event.merchant_id,
            _simulated_payment_provider,
            provider_name=provider,
        ).reconcile(event)
    if case is not None and not result.duplicate and is_open(RecoveryCaseStatus(case.status)):
        case_id = case.id
        # Each application service owns a complete transaction; end any read transaction
        # opened while returning the case before starting analysis.
        session.rollback()
        scoring_config = ScoringConfig(
            base_probability_percent=settings.scoring_base_probability_percent,
            temporary_timeout_adjustment_percent=settings.scoring_timeout_adjustment_percent,
            incident_penalty_percent=settings.scoring_incident_penalty_percent,
            priority_confidence_weight_percent=settings.scoring_confidence_weight_percent,
            version=settings.scoring_version,
        )
        CaseAnalysisService(session, event.merchant_id, scoring_config).analyze(case_id)
        session.rollback()
        # The external provider adapter is selected once provider configuration is approved.
        # Until then, the same persistence path records the deterministic safe fallback.
        AIRecommendationService(session, event.merchant_id, provider=None).fallback(case_id)
    return result


def _prepare_simulated_reconciliation(event: RevenueEvent) -> None:
    """Map a synthetic webhook to the simulated provider's authoritative status."""
    if event.payment_id is None:
        return
    status_by_event = {
        RevenueEventType.PAYMENT_SUCCEEDED: PaymentStatus.SUCCEEDED,
        RevenueEventType.INVOICE_PAID: PaymentStatus.SUCCEEDED,
        RevenueEventType.PAYMENT_REFUNDED: PaymentStatus.REFUNDED,
        RevenueEventType.PAYMENT_REVERSED: PaymentStatus.REVERSED,
    }
    _simulated_payment_provider.set_status(
        event.merchant_id,
        event.payment_id,
        status_by_event[event.event_type],
        amount_minor_units=event.amount_minor_units,
        currency=event.currency,
        provider_reference=f"sim_payment_{event.payment_id}",
    )
