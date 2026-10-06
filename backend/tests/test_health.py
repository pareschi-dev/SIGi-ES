"""Tests for the local, non-production health endpoint."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.file_monitor import DirectoryMonitor
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
    assert response.json() == {
        "enabled": False,
        "running": False,
        "status": "inativo",
        "root": None,
    }


def test_monitor_status_returns_active_state_and_configured_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monitor = DirectoryMonitor(tmp_path)
    monitor.start()
    monkeypatch.setattr(client.app.state, "file_monitor", monitor, raising=False)
    try:
        response = client.get("/api/v1/monitor/status")
    finally:
        monitor.stop()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ativo"
    assert payload["running"] is True
    assert payload["root"] == str(tmp_path.resolve())
