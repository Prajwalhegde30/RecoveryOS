import asyncio

from fastapi.testclient import TestClient
from starlette.requests import Request

from app.config import get_settings
from app.main import app, safe_unhandled_exception


def test_requests_receive_or_preserve_safe_correlation_id() -> None:
    response = TestClient(app).get("/health/live", headers={"X-Correlation-Id": "workflow_123"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "workflow_123"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"


def test_high_risk_request_family_is_rate_limited() -> None:
    settings = get_settings()
    previous_maximum = settings.rate_limit_max_requests
    previous_window = settings.rate_limit_window_seconds
    settings.rate_limit_max_requests = 1
    settings.rate_limit_window_seconds = 60
    client = TestClient(app)
    path = "/webhooks/rate-limit-test"
    try:
        first = client.post(path)
        second = client.post(path)
        assert first.status_code == 401
        assert second.status_code == 429
        assert second.json()["retryable"] is True
        assert "Retry-After" in second.headers
    finally:
        settings.rate_limit_max_requests = previous_maximum
        settings.rate_limit_window_seconds = previous_window


def test_unhandled_error_response_is_safe_and_correlated() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/cases",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        }
    )
    request.state.correlation_id = "workflow-safe"
    response = asyncio.run(
        safe_unhandled_exception(request, RuntimeError("secret database password"))
    )
    assert response.status_code == 500
    assert response.body is not None
    assert b"secret database password" not in response.body
    assert b"workflow-safe" in response.body
