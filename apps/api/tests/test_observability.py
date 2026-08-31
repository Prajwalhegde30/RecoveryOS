from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


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
