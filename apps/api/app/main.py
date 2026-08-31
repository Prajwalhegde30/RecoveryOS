from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.ai.service import AIRecommendationService
from app.api.dependencies import get_db_session
from app.api.routes import router as recovery_router
from app.cases.service import RecoveryCaseService
from app.cases.state_machine import is_open
from app.config import get_settings
from app.customers.service import CustomerOptOutService
from app.events.contracts import EventIngestionResult, RevenueEvent, RevenueEventType
from app.events.security import verify_signature
from app.events.service import EventIngestionService
from app.persistence.models import RecoveryCaseStatus
from app.scoring.economics import ScoringConfig
from app.scoring.service import CaseAnalysisService

settings = get_settings()
app = FastAPI(title="RecoveryOS API", version="0.1.0")
app.include_router(recovery_router)
db_session_dependency = Depends(get_db_session)


@app.get("/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def readiness() -> dict[str, str]:
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
