from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.enums import (
    AlertNotificationChannelType,
    AlertNotificationDeliveryStatus,
    AlertNotificationEventType,
    AlertSeverity,
)
from app.models.alert import Alert
from app.models.alert_notification import (
    AlertNotificationChannel,
    AlertNotificationDelivery,
    AlertNotificationPolicy,
)
from app.schemas.alert_notification import (
    AlertNotificationChannelCreate,
    AlertNotificationChannelRead,
    AlertNotificationChannelUpdate,
    AlertNotificationDeliveryRead,
    AlertNotificationPolicyCreate,
    AlertNotificationPolicyUpdate,
)
from app.services.encryption import EncryptionService


class AlertNotificationNotFoundError(RuntimeError):
    pass


class AlertNotificationConflictError(RuntimeError):
    pass


class AlertNotificationSecretError(RuntimeError):
    pass


class AlertNotificationService:
    summary_limit = 500
    max_attempts = 3
    retry_delays = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15))

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.encryption = EncryptionService(settings)

    def list_channels(self, session: Session) -> tuple[int, list[AlertNotificationChannel]]:
        statement = select(AlertNotificationChannel).order_by(AlertNotificationChannel.id.asc())
        total = session.scalar(select(func.count(AlertNotificationChannel.id))) or 0
        return total, list(session.scalars(statement))

    def get_channel(self, session: Session, channel_id: int) -> AlertNotificationChannel:
        channel = session.get(AlertNotificationChannel, channel_id)
        if channel is None:
            raise AlertNotificationNotFoundError(f"通知通道不存在：{channel_id}")
        return channel

    def create_channel(
        self,
        session: Session,
        payload: AlertNotificationChannelCreate,
    ) -> AlertNotificationChannel:
        self._require_encryption()
        secret = {"webhook_url": payload.webhook_url, "headers": payload.headers}
        channel = AlertNotificationChannel(
            name=payload.name,
            channel_type=payload.channel_type.value,
            enabled=payload.enabled,
            config=self._public_config(payload.webhook_url, payload.headers, payload.timeout_seconds),
            secret_config_encrypted=self._encrypt_secret(secret),
        )
        session.add(channel)
        session.flush()
        session.refresh(channel)
        return channel

    def update_channel(
        self,
        session: Session,
        channel_id: int,
        payload: AlertNotificationChannelUpdate,
    ) -> AlertNotificationChannel:
        channel = self.get_channel(session, channel_id)
        secret = self._decrypt_secret(channel)
        changed_secret = False
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates:
            channel.name = payload.name or channel.name
        if "enabled" in updates:
            channel.enabled = bool(payload.enabled)
        if "webhook_url" in updates and payload.webhook_url is not None:
            self._require_encryption()
            secret["webhook_url"] = payload.webhook_url
            changed_secret = True
        if "headers" in updates and payload.headers is not None:
            self._require_encryption()
            secret["headers"] = payload.headers
            changed_secret = True
        timeout_seconds = payload.timeout_seconds if payload.timeout_seconds is not None else self._timeout_seconds(channel)
        if changed_secret:
            channel.secret_config_encrypted = self._encrypt_secret(secret)
        if changed_secret or payload.timeout_seconds is not None:
            channel.config = self._public_config(
                str(secret.get("webhook_url") or ""),
                self._headers_from_secret(secret),
                timeout_seconds,
            )
        session.flush()
        session.refresh(channel)
        return channel

    def delete_channel(self, session: Session, channel_id: int) -> None:
        channel = self.get_channel(session, channel_id)
        policy_count = session.scalar(
            select(func.count(AlertNotificationPolicy.id)).where(AlertNotificationPolicy.channel_id == channel_id)
        ) or 0
        if policy_count:
            raise AlertNotificationConflictError("请先删除关联通知策略，再删除通知通道")
        session.delete(channel)
        session.flush()

    def test_channel(self, session: Session, channel_id: int) -> AlertNotificationChannel:
        channel = self.get_channel(session, channel_id)
        payload = {
            "event_type": "test",
            "alert": {
                "id": None,
                "title": "Webhook 测试通知",
                "severity": "critical",
                "status": "open",
                "source_type": "system",
                "alert_type": "test",
                "device_id": None,
                "message": "这是一条来自远程终端平台的测试通知",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "platform": {"service_name": self.settings.service_name},
        }
        try:
            status_code, summary = self._deliver_webhook(channel, payload)
            channel.last_test_status = AlertNotificationDeliveryStatus.success.value
            channel.last_test_at = datetime.now(timezone.utc)
            channel.last_error = None
            channel.config = {**(channel.config or {}), "last_response_status_code": status_code, "last_response_summary": summary}
        except Exception as exc:
            channel.last_test_status = AlertNotificationDeliveryStatus.failed.value
            channel.last_test_at = datetime.now(timezone.utc)
            channel.last_error = self._truncate(str(exc))
        session.flush()
        session.refresh(channel)
        return channel

    def channel_read(self, channel: AlertNotificationChannel) -> AlertNotificationChannelRead:
        config = channel.config or {}
        return AlertNotificationChannelRead(
            id=channel.id,
            name=channel.name,
            channel_type=channel.channel_type,
            enabled=channel.enabled,
            webhook_url_preview=config.get("webhook_url_preview"),
            timeout_seconds=int(config.get("timeout_seconds") or 5),
            header_keys=list(config.get("header_keys") or []),
            secret_configured=bool(config.get("secret_configured")),
            last_test_status=channel.last_test_status,
            last_test_at=channel.last_test_at,
            last_error=channel.last_error,
            created_at=channel.created_at,
            updated_at=channel.updated_at,
        )

    def list_policies(self, session: Session) -> tuple[int, list[AlertNotificationPolicy]]:
        statement = select(AlertNotificationPolicy).order_by(AlertNotificationPolicy.id.asc())
        total = session.scalar(select(func.count(AlertNotificationPolicy.id))) or 0
        return total, list(session.scalars(statement))

    def get_policy(self, session: Session, policy_id: int) -> AlertNotificationPolicy:
        policy = session.get(AlertNotificationPolicy, policy_id)
        if policy is None:
            raise AlertNotificationNotFoundError(f"通知策略不存在：{policy_id}")
        return policy

    def create_policy(self, session: Session, payload: AlertNotificationPolicyCreate) -> AlertNotificationPolicy:
        self.get_channel(session, payload.channel_id)
        policy = AlertNotificationPolicy(
            name=payload.name,
            enabled=payload.enabled,
            channel_id=payload.channel_id,
            min_severity=payload.min_severity.value,
            source_types=[item.value for item in payload.source_types],
            alert_statuses=list(payload.alert_statuses),
            event_types=[item.value for item in payload.event_types] or [AlertNotificationEventType.triggered.value],
        )
        session.add(policy)
        session.flush()
        session.refresh(policy)
        return policy

    def update_policy(
        self,
        session: Session,
        policy_id: int,
        payload: AlertNotificationPolicyUpdate,
    ) -> AlertNotificationPolicy:
        policy = self.get_policy(session, policy_id)
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates and payload.name is not None:
            policy.name = payload.name
        if "enabled" in updates and payload.enabled is not None:
            policy.enabled = payload.enabled
        if "channel_id" in updates and payload.channel_id is not None:
            self.get_channel(session, payload.channel_id)
            policy.channel_id = payload.channel_id
        if "min_severity" in updates and payload.min_severity is not None:
            policy.min_severity = payload.min_severity.value
        if "source_types" in updates and payload.source_types is not None:
            policy.source_types = [item.value for item in payload.source_types]
        if "alert_statuses" in updates and payload.alert_statuses is not None:
            policy.alert_statuses = list(payload.alert_statuses)
        if "event_types" in updates and payload.event_types is not None:
            policy.event_types = [item.value for item in payload.event_types] or [AlertNotificationEventType.triggered.value]
        session.flush()
        session.refresh(policy)
        return policy

    def delete_policy(self, session: Session, policy_id: int) -> None:
        policy = self.get_policy(session, policy_id)
        session.delete(policy)
        session.flush()

    def list_deliveries(
        self,
        session: Session,
        *,
        offset: int,
        limit: int,
        status: str | None = None,
        alert_id: int | None = None,
        channel_id: int | None = None,
    ) -> tuple[int, list[AlertNotificationDeliveryRead]]:
        statement = select(AlertNotificationDelivery)
        count_statement = select(func.count(AlertNotificationDelivery.id))
        filters: list[Any] = []
        if status:
            filters.append(AlertNotificationDelivery.status == status)
        if alert_id is not None:
            filters.append(AlertNotificationDelivery.alert_id == alert_id)
        if channel_id is not None:
            filters.append(AlertNotificationDelivery.channel_id == channel_id)
        for condition in filters:
            statement = statement.where(condition)
            count_statement = count_statement.where(condition)
        total = session.scalar(count_statement) or 0
        deliveries = list(
            session.scalars(
                statement.order_by(AlertNotificationDelivery.created_at.desc(), AlertNotificationDelivery.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return total, [self.delivery_read(session, delivery) for delivery in deliveries]

    def delivery_read(self, session: Session, delivery: AlertNotificationDelivery) -> AlertNotificationDeliveryRead:
        alert = session.get(Alert, delivery.alert_id)
        channel = session.get(AlertNotificationChannel, delivery.channel_id)
        policy = session.get(AlertNotificationPolicy, delivery.policy_id)
        return AlertNotificationDeliveryRead(
            id=delivery.id,
            alert_id=delivery.alert_id,
            channel_id=delivery.channel_id,
            policy_id=delivery.policy_id,
            event_type=delivery.event_type,
            status=delivery.status,
            attempt_count=delivery.attempt_count,
            last_attempt_at=delivery.last_attempt_at,
            next_retry_at=delivery.next_retry_at,
            response_status_code=delivery.response_status_code,
            response_summary=delivery.response_summary,
            error_message=delivery.error_message,
            alert_title=alert.title if alert else None,
            channel_name=channel.name if channel else None,
            policy_name=policy.name if policy else None,
            created_at=delivery.created_at,
            updated_at=delivery.updated_at,
        )

    def summary(self, session: Session) -> dict[str, Any]:
        enabled_channel_count = session.scalar(
            select(func.count(AlertNotificationChannel.id)).where(AlertNotificationChannel.enabled.is_(True))
        ) or 0
        enabled_policy_count = session.scalar(
            select(func.count(AlertNotificationPolicy.id)).where(AlertNotificationPolicy.enabled.is_(True))
        ) or 0
        failed_delivery_count = session.scalar(
            select(func.count(AlertNotificationDelivery.id)).where(AlertNotificationDelivery.status == AlertNotificationDeliveryStatus.failed.value)
        ) or 0
        retrying_delivery_count = session.scalar(
            select(func.count(AlertNotificationDelivery.id)).where(AlertNotificationDelivery.status == AlertNotificationDeliveryStatus.retrying.value)
        ) or 0
        last_delivery_at = session.scalar(select(func.max(AlertNotificationDelivery.created_at)))
        warnings: list[str] = []
        if enabled_policy_count and not enabled_channel_count:
            warnings.append("存在启用通知策略，但没有启用通知通道")
        if failed_delivery_count:
            warnings.append("存在失败的告警通知投递，请检查 Webhook 配置")
        if retrying_delivery_count:
            warnings.append("存在等待重试的告警通知投递")
        return {
            "enabled_channel_count": enabled_channel_count,
            "enabled_policy_count": enabled_policy_count,
            "failed_delivery_count": failed_delivery_count,
            "retrying_delivery_count": retrying_delivery_count,
            "last_delivery_at": last_delivery_at,
            "warnings": warnings,
        }

    def record_event(self, session: Session, alert: Alert, event_type: str) -> list[AlertNotificationDelivery]:
        created: list[AlertNotificationDelivery] = []
        policies = list(session.scalars(select(AlertNotificationPolicy).where(AlertNotificationPolicy.enabled.is_(True))))
        for policy in policies:
            channel = session.get(AlertNotificationChannel, policy.channel_id)
            if channel is None or not channel.enabled:
                continue
            if not self._policy_matches(policy, alert, event_type):
                continue
            existing = session.scalar(
                select(AlertNotificationDelivery).where(
                    AlertNotificationDelivery.alert_id == alert.id,
                    AlertNotificationDelivery.channel_id == channel.id,
                    AlertNotificationDelivery.policy_id == policy.id,
                    AlertNotificationDelivery.event_type == event_type,
                )
            )
            if existing is not None:
                continue
            delivery = AlertNotificationDelivery(
                alert_id=alert.id,
                channel_id=channel.id,
                policy_id=policy.id,
                event_type=event_type,
                status=AlertNotificationDeliveryStatus.pending.value,
                attempt_count=0,
            )
            session.add(delivery)
            session.flush()
            self.process_delivery(session, delivery)
            created.append(delivery)
        session.flush()
        return created

    def retry_delivery(self, session: Session, delivery_id: int) -> AlertNotificationDelivery:
        delivery = session.get(AlertNotificationDelivery, delivery_id)
        if delivery is None:
            raise AlertNotificationNotFoundError(f"通知投递记录不存在：{delivery_id}")
        self.process_delivery(session, delivery, manual=True)
        session.flush()
        session.refresh(delivery)
        return delivery

    def process_delivery(
        self,
        session: Session,
        delivery: AlertNotificationDelivery,
        *,
        manual: bool = False,
    ) -> AlertNotificationDelivery:
        channel = self.get_channel(session, delivery.channel_id)
        alert = session.get(Alert, delivery.alert_id)
        if alert is None:
            delivery.status = AlertNotificationDeliveryStatus.skipped.value
            delivery.error_message = "关联告警不存在"
            return delivery
        now = datetime.now(timezone.utc)
        if not manual and delivery.next_retry_at is not None and delivery.next_retry_at > now:
            return delivery
        payload = self._webhook_payload(alert, delivery.event_type)
        delivery.attempt_count += 1
        delivery.last_attempt_at = now
        try:
            status_code, summary = self._deliver_webhook(channel, payload)
            delivery.status = AlertNotificationDeliveryStatus.success.value
            delivery.response_status_code = status_code
            delivery.response_summary = summary
            delivery.error_message = None
            delivery.next_retry_at = None
        except Exception as exc:
            delivery.response_status_code = None
            delivery.response_summary = None
            delivery.error_message = self._truncate(str(exc))
            if delivery.attempt_count >= self.max_attempts:
                delivery.status = AlertNotificationDeliveryStatus.failed.value
                delivery.next_retry_at = None
            else:
                delivery.status = AlertNotificationDeliveryStatus.retrying.value
                delay = self.retry_delays[min(delivery.attempt_count - 1, len(self.retry_delays) - 1)]
                delivery.next_retry_at = now + delay
        return delivery

    def _policy_matches(self, policy: AlertNotificationPolicy, alert: Alert, event_type: str) -> bool:
        event_types = policy.event_types or [AlertNotificationEventType.triggered.value]
        if event_type not in event_types:
            return False
        if policy.source_types and alert.source_type not in policy.source_types:
            return False
        if policy.alert_statuses and alert.status not in policy.alert_statuses:
            return False
        return self._severity_rank(alert.severity) >= self._severity_rank(policy.min_severity)

    def _deliver_webhook(self, channel: AlertNotificationChannel, payload: dict[str, Any]) -> tuple[int, str]:
        if channel.channel_type != AlertNotificationChannelType.webhook.value:
            raise RuntimeError("当前仅支持 Webhook 通知通道")
        secret = self._decrypt_secret(channel)
        url = str(secret.get("webhook_url") or "")
        if not url:
            raise RuntimeError("Webhook URL 未配置")
        headers = self._headers_from_secret(secret)
        timeout_seconds = self._timeout_seconds(channel)
        response = httpx.post(url, json=payload, headers=headers, timeout=timeout_seconds)
        summary = self._truncate(response.text or response.reason_phrase)
        if response.status_code >= 400:
            raise RuntimeError(f"Webhook 返回 HTTP {response.status_code}: {summary}")
        return response.status_code, summary or "ok"

    def _webhook_payload(self, alert: Alert, event_type: str) -> dict[str, Any]:
        return {
            "event_type": event_type,
            "alert": {
                "id": alert.id,
                "title": alert.title,
                "severity": alert.severity,
                "status": alert.status,
                "source_type": alert.source_type,
                "alert_type": alert.alert_type,
                "device_id": alert.device_id,
                "message": self._truncate(alert.summary),
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
            },
            "platform": {"service_name": self.settings.service_name},
        }

    def _require_encryption(self) -> None:
        if not self.encryption.enabled:
            raise AlertNotificationSecretError("未配置 CREDENTIAL_ENCRYPTION_KEY，不能保存 Webhook 敏感配置")

    def _encrypt_secret(self, value: dict[str, Any]) -> str:
        self._require_encryption()
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True)
        encrypted = self.encryption.encrypt_optional(raw)
        if encrypted == raw:
            raise AlertNotificationSecretError("Webhook 敏感配置未加密，已拒绝保存")
        return encrypted or ""

    def _decrypt_secret(self, channel: AlertNotificationChannel) -> dict[str, Any]:
        encrypted = channel.secret_config_encrypted
        if not encrypted:
            return {}
        raw = self.encryption.decrypt_optional(encrypted)
        if not raw:
            return {}
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Webhook 敏感配置无法解析，请检查加密密钥") from exc
        return decoded if isinstance(decoded, dict) else {}

    def _public_config(self, webhook_url: str, headers: dict[str, str], timeout_seconds: int) -> dict[str, Any]:
        return {
            "webhook_url_preview": self._mask_url(webhook_url),
            "timeout_seconds": timeout_seconds,
            "header_keys": sorted(headers.keys()),
            "secret_configured": bool(webhook_url),
        }

    def _timeout_seconds(self, channel: AlertNotificationChannel) -> int:
        return int((channel.config or {}).get("timeout_seconds") or 5)

    def _headers_from_secret(self, secret: dict[str, Any]) -> dict[str, str]:
        headers = secret.get("headers") or {}
        if not isinstance(headers, dict):
            return {}
        return {str(key): str(value) for key, value in headers.items()}

    def _mask_url(self, url: str) -> str:
        try:
            parts = urlsplit(url)
        except ValueError:
            return "已配置"
        query = parse_qsl(parts.query, keep_blank_values=True)
        masked_query = [(key, "***" if value else value) for key, value in query]
        netloc = parts.netloc
        return urlunsplit((parts.scheme, netloc, parts.path, urlencode(masked_query), ""))

    def _severity_rank(self, severity: str) -> int:
        if severity == AlertSeverity.critical.value:
            return 2
        if severity == AlertSeverity.warning.value:
            return 1
        return 0

    def _truncate(self, value: str | None) -> str | None:
        if value is None:
            return None
        return value if len(value) <= self.summary_limit else value[: self.summary_limit] + "...[已截断]"
