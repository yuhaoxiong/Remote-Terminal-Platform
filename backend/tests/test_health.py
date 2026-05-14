from fastapi.testclient import TestClient

from app.main import create_app


def test_health_check_reports_service_ready() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "edge-platform",
        "version": "0.1.0",
        "database": "ok",
    }
