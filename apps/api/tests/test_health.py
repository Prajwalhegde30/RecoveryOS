from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

import app.main as main_module
from app.api.routes import operational_health
from app.main import app

client = TestClient(app)


def test_liveness() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness(monkeypatch) -> None:
    class HealthySession:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def execute(self, *_args) -> None:
            return None

    class HealthyFactory:
        def __call__(self):
            return HealthySession()

    monkeypatch.setattr(main_module, "get_session_factory", lambda: HealthyFactory())
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_reports_database_degradation_without_internal_details(monkeypatch) -> None:
    class BrokenSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def execute(self, *_args):
            raise OperationalError("SELECT 1", {}, RuntimeError("database secret"))

    class BrokenFactory:
        def __call__(self):
            return BrokenSession()

    monkeypatch.setattr(main_module, "get_session_factory", lambda: BrokenFactory())
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "database readiness check failed"}
    assert "database secret" not in response.text


def test_operational_health_returns_safe_degraded_database_state() -> None:
    class BrokenSession:
        def scalar(self, *_args):
            raise OperationalError("SELECT", {}, RuntimeError("database secret"))

    response = operational_health(merchant_id="merchant-1", session=BrokenSession())
    assert response.components["database"].status == "degraded"
    assert response.components["database"].detail == "database health data is unavailable"
    assert response.components["worker"].status == "unknown"
