from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.config import get_settings
from app.events.contracts import EventIngestionResult, RevenueEvent
from app.events.security import verify_signature
from app.events.service import EventIngestionService

settings = get_settings()
app = FastAPI(title="RecoveryOS API", version="0.1.0")
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
    return EventIngestionService(session, provider).ingest(event)
