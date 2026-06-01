from collections.abc import Iterator

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import init_db, session_scope
from app.main import create_app
from app.models.alert import Alert
from app.models.alert_notification import AlertNotificationDelivery


@pytest.fixture()
def encrypted_client(settings: Settings, tmp_path) -> Iterator[TestClient]:
    local_settings = settings.model_copy(
        update={
            "database_url": f"sqlite:///{tmp_path / 'api-encrypted.db'}",
            "credential_encryption_key": Fernet.generate_key().decode("utf-8"),
        }
    )
    init_db(local_settings)
    with TestClient(create_app(local_settings)) as test_client:
        test_client.app.state.test_settings = local_settings
        yield test_client


@pytest.fixture()
def encrypted_headers(encrypted_client: TestClient) -> dict[str, str]:
    response = encrypted_client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_channel_api_rejects_secret_without_encryption(client, auth_headers) -> None:
    response = client.post(
        "/api/alert-notification-channels",
        headers=auth_headers,
        json={"name": "Webhook", "webhook_url": "https://example.com/hook?token=secret"},
    )
    assert response.status_code == 400
    assert "CREDENTIAL_ENCRYPTION_KEY" in response.json()["detail"]


def test_channel_policy_delivery_api_flow(encrypted_client, encrypted_headers, monkeypatch) -> None:
    calls: list[dict] = []

    def fake_post(url, json, headers, timeout):
        calls.append(json)

        class Response:
            status_code = 200
            text = "ok"
            reason_phrase = "OK"

        return Response()

    monkeypatch.setattr("app.services.alert_notification_service.httpx.post", fake_post)

    create_channel = encrypted_client.post(
        "/api/alert-notification-channels",
        headers=encrypted_headers,
        json={
            "name": "Webhook",
            "webhook_url": "https://example.com/hook?token=secret",
            "headers": {"Authorization": "Bearer secret"},
            "timeout_seconds": 3,
        },
    )
    assert create_channel.status_code == 201
    channel = create_channel.json()
    assert channel["secret_configured"] is True
    assert "secret" not in channel["webhook_url_preview"]
    assert channel["header_keys"] == ["Authorization"]

    create_policy = encrypted_client.post(
        "/api/alert-notification-policies",
        headers=encrypted_headers,
        json={"name": "只通知严重告警", "channel_id": channel["id"]},
    )
    assert create_policy.status_code == 201
    policy = create_policy.json()
    assert policy["min_severity"] == "critical"
    assert policy["event_types"] == ["triggered"]

    with session_scope(encrypted_client.app.state.test_settings) as session:
        alert = Alert(
            dedupe_key="api:alert",
            alert_type="cpu_high",
            severity="critical",
            status="open",
            source_type="metric",
            source_id=1,
            title="CPU 高负载",
            summary="CPU 99%",
        )
        session.add(alert)
        session.flush()
        alert_id = alert.id

    # Reuse the public alert acknowledge path later; direct event generation is covered by service tests.
    test_response = encrypted_client.post(
        f"/api/alert-notification-channels/{channel['id']}/test",
        headers=encrypted_headers,
    )
    assert test_response.status_code == 200
    assert test_response.json()["last_test_status"] == "success"
    assert calls[-1]["event_type"] == "test"

    with session_scope(encrypted_client.app.state.test_settings) as session:
        session.add(
            AlertNotificationDelivery(
                alert_id=alert_id,
                channel_id=channel["id"],
                policy_id=policy["id"],
                event_type="triggered",
                status="failed",
                attempt_count=3,
                error_message="network down",
            )
        )

    list_deliveries = encrypted_client.get("/api/alert-notification-deliveries", headers=encrypted_headers)
    assert list_deliveries.status_code == 200
    assert list_deliveries.json()["total"] == 1
    delivery_id = list_deliveries.json()["items"][0]["id"]
    assert list_deliveries.json()["items"][0]["alert_title"] == "CPU 高负载"

    retry = encrypted_client.post(
        f"/api/alert-notification-deliveries/{delivery_id}/retry",
        headers=encrypted_headers,
    )
    assert retry.status_code == 200
    assert retry.json()["status"] == "success"

    blocked_delete = encrypted_client.delete(
        f"/api/alert-notification-channels/{channel['id']}",
        headers=encrypted_headers,
    )
    assert blocked_delete.status_code == 409

    delete_policy = encrypted_client.delete(
        f"/api/alert-notification-policies/{policy['id']}",
        headers=encrypted_headers,
    )
    assert delete_policy.status_code == 204

    delete_channel = encrypted_client.delete(
        f"/api/alert-notification-channels/{channel['id']}",
        headers=encrypted_headers,
    )
    assert delete_channel.status_code == 204


def test_notification_api_requires_authentication(client) -> None:
    response = client.get("/api/alert-notification-channels")
    assert response.status_code == 403
