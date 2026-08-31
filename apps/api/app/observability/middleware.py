from __future__ import annotations

import logging
import secrets
import threading
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.config import get_settings

logger = logging.getLogger("recoveryos.request")


class _WindowLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[float, int]] = {}

    def allow(self, key: str, *, maximum: int, window_seconds: int) -> bool:
        now = time.monotonic()
        with self._lock:
            started, count = self._windows.get(key, (now, 0))
            if now - started >= window_seconds:
                started, count = now, 0
            if count >= maximum:
                self._windows[key] = (started, count)
                return False
            self._windows[key] = (started, count + 1)
            if len(self._windows) > 10_000:
                self._windows = {
                    stored_key: value
                    for stored_key, value in self._windows.items()
                    if now - value[0] < window_seconds
                }
            return True


class CorrelationRateLimitMiddleware(BaseHTTPMiddleware):
    """Adds safe correlation metadata and limits high-risk request families."""

    _LIMITED_PREFIXES = ("/webhooks/", "/api/v1/simulator")

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._limiter = _WindowLimiter()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = _correlation_id(request.headers.get("X-Correlation-Id"))
        request.state.correlation_id = correlation_id
        settings = get_settings()
        if request.url.path.startswith(self._LIMITED_PREFIXES):
            client = request.client.host if request.client else "unknown"
            key = f"{client}:{request.url.path}"
            if not self._limiter.allow(
                key,
                maximum=settings.rate_limit_max_requests,
                window_seconds=settings.rate_limit_window_seconds,
            ):
                response: Response = JSONResponse(
                    status_code=429,
                    content={
                        "detail": "request rate limit exceeded",
                        "retryable": True,
                        "correlation_id": correlation_id,
                    },
                )
                response.headers["Retry-After"] = str(settings.rate_limit_window_seconds)
                response.headers["X-Correlation-Id"] = correlation_id
                return response
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            logger.info(
                "request_completed",
                extra={
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                },
            )
        response.headers["X-Correlation-Id"] = correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if settings.app_env.lower() == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response


def _correlation_id(value: str | None) -> str:
    if (
        value
        and len(value) <= 128
        and all(character.isalnum() or character in "-_." for character in value)
    ):
        return value
    return f"req_{secrets.token_hex(12)}"
