"""Tests for the local, non-production health endpoint."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_marks_local_unverified_mode_and_disabled_integrations() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "environment": "local_unverified",
        "database": "connected",
        "database_engine": "sqlite",
        "integrations_enabled": False,
    }


def test_health_does_not_expose_connection_credentials_or_url() -> None:
    response = client.get("/api/v1/health")
    body = response.text.lower()

    assert "postgresql+psycopg://" not in body
    assert "password" not in body
    assert "username" not in body


def test_monitor_status_is_disabled_without_explicit_root() -> None:
    response = client.get("/api/v1/monitor/status")

    assert response.status_code == 200
    assert response.json() == {"enabled": False, "running": False}
