import sys
from pathlib import Path
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.main import app  # noqa: E402


def test_app_imports_and_health_is_safe(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setenv("JWT_SECRET", "must-not-leak")
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["database"] == "not_configured"
    assert "must-not-leak" not in response.text


def test_system_info_is_safe():
    with TestClient(app) as client:
        response = client.get("/api/v1/system/info")
    assert response.status_code == 200
    assert "mongodb_uri" not in response.text.lower()


def test_root_endpoint_returns_successfully():
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
