from cryptography.fernet import Fernet

from app.config import Settings
from app.database import init_db, session_scope
from app.enums import AlertNotificationDeliveryStatus
from app.models.alert import Alert
from app.models.alert_notification import (
    AlertNotificationChannel,
    AlertNotificationDelivery,
    AlertNotificationPolicy,
)
from app.services.alert_notification_service import AlertNotificationSecretError, AlertNotificationService
from app.schemas.alert_notification import AlertNotificationChannelCreate, AlertNotificationPolicyCreate


def encrypted_settings(settings: Settings, tmp_path) -> Settings:
    return settings.model_copy(
        update={
            "database_url": f"sqlite:///{tmp_path / 'encrypted.db'}",
            "credential_encryption_key": Fernet.generate_key().decode("utf-8"),
        }
    )


def test_webhook_channel_requires_encryption(initialized_settings) -> None:
    with session_scope(initialized_settings) as session:
        service = AlertNotificationService(initialized_settings)
        try:
            service.create_channel(
                session,
                AlertNotificationChannelCreate(
                    name="未加密 Webhook",
                    webhook_url="https://example.com/hook?token=secret",
                    headers={"Authorization": "Bearer secret"},
                ),
            )
        except AlertNotificationSecretError as exc:
            assert "CREDENTIAL_ENCRYPTION_KEY" in str(exc)
        else:
            raise AssertionError("缺少加密密钥时不应允许保存 Webhook secret")


def test_channel_create_masks_secret_and_decrypts_for_delivery(settings, tmp_path) -> None:
    local_settings = encrypted_settings(settings, tmp_path)
    init_db(local_settings)
    with session_scope(local_settings) as session:
        service = AlertNotificationService(local_settings)
        channel = service.create_channel(
            session,
            AlertNotificationChannelCreate(
                name="Webhook",
                webhook_url="https://example.com/hook?token=secret",
                headers={"Authorization": "Bearer secret"},
                timeout_seconds=3,
            ),
        )
        assert "secret" not in channel.secret_config_encrypted
        read = service.channel_read(channel)
        assert read.secret_configured is True
        assert read.timeout_seconds == 3
        assert read.header_keys == ["Authorization"]
        assert "secret" not in (read.webhook_url_preview or "")


def test_policy_matching_creates_single_delivery(settings, tmp_path, monkeypatch) -> None:
    local_settings = encrypted_settings(settings, tmp_path)
    init_db(local_settings)
    calls: list[tuple[str, dict]] = []

    def fake_post(url, json, headers, timeout):
        calls.append((url, json))

        class Response:
            status_code = 200
            text = "ok"
            reason_phrase = "OK"

        return Response()

    monkeypatch.setattr("app.services.alert_notification_service.httpx.post", fake_post)
    with session_scope(local_settings) as session:
        service = AlertNotificationService(local_settings)
        channel = service.create_channel(
            session,
            AlertNotificationChannelCreate(name="Webhook", webhook_url="https://example.com/hook"),
        )
        policy = service.create_policy(
            session,
            AlertNotificationPolicyCreate(name="严重告警", channel_id=channel.id),
        )
        alert = Alert(
            dedupe_key="metric:cpu:1",
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

        first = service.record_event(session, alert, "triggered")
        second = service.record_event(session, alert, "triggered")

        assert len(first) == 1
        assert second == []
        delivery = session.query(AlertNotificationDelivery).one()
        assert delivery.status == AlertNotificationDeliveryStatus.success.value
        assert delivery.attempt_count == 1
        assert delivery.policy_id == policy.id
        assert calls[0][1]["alert"]["title"] == "CPU 高负载"


def test_delivery_failure_can_retry(settings, tmp_path, monkeypatch) -> None:
    local_settings = encrypted_settings(settings, tmp_path)
    init_db(local_settings)
    attempts = {"count": 0}

    def flaky_post(url, json, headers, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("network down")

        class Response:
            status_code = 200
            text = "ok"
            reason_phrase = "OK"

        return Response()

    monkeypatch.setattr("app.services.alert_notification_service.httpx.post", flaky_post)
    with session_scope(local_settings) as session:
        service = AlertNotificationService(local_settings)
        channel = service.create_channel(
            session,
            AlertNotificationChannelCreate(name="Webhook", webhook_url="https://example.com/hook"),
        )
        service.create_policy(session, AlertNotificationPolicyCreate(name="严重告警", channel_id=channel.id))
        alert = Alert(
            dedupe_key="metric:disk:1",
            alert_type="disk_high",
            severity="critical",
            status="open",
            source_type="metric",
            source_id=1,
            title="磁盘高占用",
            summary="磁盘 99%",
        )
        session.add(alert)
        session.flush()
        [delivery] = service.record_event(session, alert, "triggered")
        assert delivery.status == AlertNotificationDeliveryStatus.retrying.value
        assert delivery.next_retry_at is not None

        service.retry_delivery(session, delivery.id)
        assert delivery.status == AlertNotificationDeliveryStatus.success.value
        assert attempts["count"] == 2


def test_delete_channel_blocks_when_policy_exists(settings, tmp_path) -> None:
    local_settings = encrypted_settings(settings, tmp_path)
    init_db(local_settings)
    with session_scope(local_settings) as session:
        service = AlertNotificationService(local_settings)
        channel = service.create_channel(
            session,
            AlertNotificationChannelCreate(name="Webhook", webhook_url="https://example.com/hook"),
        )
        service.create_policy(session, AlertNotificationPolicyCreate(name="严重告警", channel_id=channel.id))
        try:
            service.delete_channel(session, channel.id)
        except RuntimeError as exc:
            assert "通知策略" in str(exc)
        else:
            raise AssertionError("被策略引用的通道不应被删除")


def test_notification_summary(initialized_settings) -> None:
    with session_scope(initialized_settings) as session:
        channel = AlertNotificationChannel(
            name="Webhook",
            channel_type="webhook",
            enabled=True,
            config={"secret_configured": True, "timeout_seconds": 5},
            secret_config_encrypted="encrypted",
        )
        session.add(channel)
        session.flush()
        policy = AlertNotificationPolicy(name="严重告警", channel_id=channel.id, enabled=True)
        session.add(policy)
        session.flush()
        alert = Alert(
            dedupe_key="test",
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
        session.add(
            AlertNotificationDelivery(
                alert_id=alert.id,
                channel_id=channel.id,
                policy_id=policy.id,
                event_type="triggered",
                status="failed",
                attempt_count=3,
            )
        )
        session.flush()
        summary = AlertNotificationService(initialized_settings).summary(session)
        assert summary["enabled_channel_count"] == 1
        assert summary["enabled_policy_count"] == 1
        assert summary["failed_delivery_count"] == 1
        assert summary["warnings"]
