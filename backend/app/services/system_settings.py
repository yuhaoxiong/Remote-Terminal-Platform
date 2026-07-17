from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import session_scope
from app.models.log import OperationLog
from app.models.system_setting import SystemSetting, SystemSettingChange
from app.models.user import User
from app.schemas.system_setting import SystemSettingEffectiveItem
from app.services.encryption import EncryptionService
from app.services.operation_log import OperationLogService


class SystemSettingError(ValueError):
    pass


class SystemSettingPermissionError(SystemSettingError):
    pass


@dataclass(frozen=True)
class SettingSpec:
    key: str
    attr: str | None
    name: str
    description: str
    category: str
    value_type: str
    editable: bool = True
    secret: bool = False
    requires_restart: bool = False
    runtime_effective: bool = True
    options: tuple[str, ...] | None = None
    min_value: int | None = None
    max_value: int | None = None


GROUPS: dict[str, str] = {
    "remote_connection": "远程连接",
    "device_credentials": "默认设备凭据",
    "file_storage": "文件与存储",
    "scheduler": "调度器",
    "alert_notification": "告警通知",
    "security_auth": "安全与认证",
    "readonly_status": "只读状态",
}


SYSTEM_SETTING_REGISTRY: dict[str, SettingSpec] = {
    "REMOTE_GATEWAY_HOST": SettingSpec("REMOTE_GATEWAY_HOST", "remote_gateway_host", "SSH 网关主机", "远程 SSH 网关主机地址", "remote_connection", "string"),
    "VNC_GATEWAY_HOST": SettingSpec("VNC_GATEWAY_HOST", "vnc_gateway_host", "VNC 网关主机", "远程 VNC 网关主机地址", "remote_connection", "string"),
    "DEFAULT_VNC_PASSWORD": SettingSpec("DEFAULT_VNC_PASSWORD", "default_vnc_password", "默认 VNC 密码", "远程 VNC 连接默认使用的密码，可在连接页临时覆盖", "remote_connection", "string", secret=True),
    "SSH_TIMEOUT_SECONDS": SettingSpec("SSH_TIMEOUT_SECONDS", "ssh_timeout_seconds", "SSH 超时", "SSH 连接超时时间", "remote_connection", "int", min_value=1, max_value=300),
    "DEPLOYMENT_TIMEOUT_SECONDS": SettingSpec("DEPLOYMENT_TIMEOUT_SECONDS", "deployment_timeout_seconds", "部署执行超时", "单个功能包下载、安装和健康检查的最长 SSH 等待时间", "remote_connection", "int", min_value=60, max_value=7200),
    "VNC_TIMEOUT_SECONDS": SettingSpec("VNC_TIMEOUT_SECONDS", "vnc_timeout_seconds", "VNC 超时", "VNC 连接超时时间", "remote_connection", "int", min_value=1, max_value=300),
    "SSH_HOST_KEY_POLICY": SettingSpec("SSH_HOST_KEY_POLICY", "ssh_host_key_policy", "SSH 主机密钥策略", "SSH known_hosts 校验策略", "remote_connection", "enum", options=("auto_add", "warning", "reject")),
    "SSH_KNOWN_HOSTS_FILE": SettingSpec("SSH_KNOWN_HOSTS_FILE", "ssh_known_hosts_file", "known_hosts 文件", "SSH known_hosts 文件路径", "remote_connection", "string"),
    "DEFAULT_DEVICE_SSH_USER": SettingSpec("DEFAULT_DEVICE_SSH_USER", "default_device_ssh_user", "默认 SSH 用户", "自动导入设备时使用的默认 SSH 用户名", "device_credentials", "string"),
    "DEFAULT_DEVICE_SSH_PASSWORD": SettingSpec("DEFAULT_DEVICE_SSH_PASSWORD", "default_device_ssh_password", "默认 SSH 密码", "自动导入设备时使用的默认 SSH 密码", "device_credentials", "string", secret=True),
    "FILE_BACKEND": SettingSpec("FILE_BACKEND", "file_backend", "文件后端", "设备文件管理使用的文件后端", "file_storage", "enum", requires_restart=True, runtime_effective=False, options=("local", "sftp")),
    "FILE_STORAGE_DIR": SettingSpec("FILE_STORAGE_DIR", "file_storage_dir", "文件存储目录", "本地文件后端存储目录", "file_storage", "string", requires_restart=True, runtime_effective=False),
    "SCHEDULER_ENABLED": SettingSpec("SCHEDULER_ENABLED", "scheduler_enabled", "启用调度器", "是否启用后台调度器", "scheduler", "bool", requires_restart=True, runtime_effective=False),
    "SCHEDULER_POLL_INTERVAL_SECONDS": SettingSpec("SCHEDULER_POLL_INTERVAL_SECONDS", "scheduler_poll_interval_seconds", "调度器扫描间隔", "后台调度器轮询间隔", "scheduler", "int", min_value=5, max_value=3600),
    "WEBHOOK_TIMEOUT_SECONDS": SettingSpec("WEBHOOK_TIMEOUT_SECONDS", "webhook_timeout_seconds", "Webhook 超时", "Webhook 请求超时时间", "alert_notification", "int", min_value=1, max_value=120),
    "WEBHOOK_MAX_RETRIES": SettingSpec("WEBHOOK_MAX_RETRIES", "webhook_max_retries", "Webhook 最大重试", "Webhook 通知最大重试次数", "alert_notification", "int", min_value=0, max_value=10),
    "NOTIFICATION_RETENTION_DAYS": SettingSpec("NOTIFICATION_RETENTION_DAYS", "notification_retention_days", "通知记录保留天数", "通知投递记录保留天数", "alert_notification", "int", min_value=1, max_value=3650),
    "ACCESS_TOKEN_EXPIRE_MINUTES": SettingSpec("ACCESS_TOKEN_EXPIRE_MINUTES", "access_token_expire_minutes", "访问令牌有效期", "Access Token 有效分钟数", "security_auth", "int", requires_restart=True, runtime_effective=False, min_value=5, max_value=1440),
    "REFRESH_TOKEN_EXPIRE_MINUTES": SettingSpec("REFRESH_TOKEN_EXPIRE_MINUTES", "refresh_token_expire_minutes", "刷新令牌有效期", "Refresh Token 有效分钟数", "security_auth", "int", requires_restart=True, runtime_effective=False, min_value=30, max_value=43200),
    "DATABASE_URL": SettingSpec("DATABASE_URL", "database_url", "数据库连接", "启动级数据库连接配置", "readonly_status", "string", editable=False),
    "CREDENTIAL_ENCRYPTION_KEY": SettingSpec("CREDENTIAL_ENCRYPTION_KEY", "credential_encryption_key", "凭据加密密钥", "启动级敏感凭据加密密钥状态", "readonly_status", "string", editable=False, secret=True),
    "JWT_SECRET_KEY": SettingSpec("JWT_SECRET_KEY", "jwt_secret_key", "JWT 密钥", "JWT 密钥状态和风险", "readonly_status", "string", editable=False, secret=True),
}


def is_systemd_managed() -> bool:
    return bool(os.getenv("INVOCATION_ID") or os.getenv("SYSTEMD_EXEC_PID"))


class SystemSettingService:
    def __init__(self, base_settings: Settings) -> None:
        self.base_settings = base_settings
        self.encryption = EncryptionService(base_settings)

    def schema_items(self) -> list[SettingSpec]:
        return list(SYSTEM_SETTING_REGISTRY.values())

    def load_effective_settings(self, *, clear_pending: bool = False, include_pending: bool = True) -> Settings:
        with session_scope(self.base_settings) as session:
            effective = self._build_effective_settings(session, include_pending=include_pending)
            if clear_pending:
                self.clear_pending_restart(session)
            return effective

    def effective_items(self, session: Session) -> list[SystemSettingEffectiveItem]:
        rows = {row.key: row for row in session.scalars(select(SystemSetting)).all()}
        return [self._effective_item(spec, rows.get(spec.key)) for spec in SYSTEM_SETTING_REGISTRY.values()]

    def save_group(
        self,
        session: Session,
        *,
        group_key: str,
        values: dict[str, Any],
        actor: User,
        client_ip: str | None,
    ) -> tuple[list[str], bool]:
        if group_key not in GROUPS:
            raise SystemSettingError(f"未知系统设置分组：{group_key}")
        updated_keys: list[str] = []
        requires_restart = False
        for key, raw_value in values.items():
            spec = SYSTEM_SETTING_REGISTRY.get(key)
            if spec is None or not spec.editable or spec.category != group_key:
                raise SystemSettingError(f"不支持的系统设置：{key}")
            value = self._validate_value(spec, raw_value)
            row = session.scalar(select(SystemSetting).where(SystemSetting.key == key))
            old_source = "database" if row else self._base_source(spec)
            old_snapshot = self._snapshot(spec, self._row_value(spec, row) if row else self._base_value(spec))
            if row is None:
                row = SystemSetting(
                    key=key,
                    category=spec.category,
                    value_type=spec.value_type,
                    source="database",
                    is_secret=spec.secret,
                    requires_restart=spec.requires_restart,
                )
                session.add(row)
            row.category = spec.category
            row.value_type = spec.value_type
            row.is_secret = spec.secret
            row.requires_restart = spec.requires_restart
            row.pending_restart = spec.requires_restart
            row.is_valid = True
            row.invalid_reason = None
            row.updated_by = actor.id
            if spec.secret:
                row.value_json = None
                row.secret_value_encrypted = self._encrypt_secret(value)
            else:
                row.value_json = value
                row.secret_value_encrypted = None
            self._record_change(
                session,
                spec=spec,
                action="save",
                old_source=old_source,
                new_source="database",
                old_value=old_snapshot,
                new_value=self._snapshot(spec, value),
                pending_restart=row.pending_restart,
                actor=actor,
                client_ip=client_ip,
            )
            updated_keys.append(key)
            requires_restart = requires_restart or spec.requires_restart
        OperationLogService(self.base_settings).record(
            session,
            user_id=actor.id,
            action="system_settings.save",
            target_type="system_settings",
            target_id=None,
            status="success",
            detail=f"{group_key}: {','.join(updated_keys)}",
        )
        session.flush()
        return updated_keys, requires_restart

    def reset(
        self,
        session: Session,
        *,
        key: str,
        actor: User,
        client_ip: str | None,
    ) -> SettingSpec:
        spec = SYSTEM_SETTING_REGISTRY.get(key)
        if spec is None or not spec.editable:
            raise SystemSettingError(f"不支持的系统设置：{key}")
        row = session.scalar(select(SystemSetting).where(SystemSetting.key == key))
        old_snapshot = self._snapshot(spec, self._row_value(spec, row) if row else self._base_value(spec))
        if row is not None:
            session.delete(row)
        self._record_change(
            session,
            spec=spec,
            action="reset",
            old_source="database" if row else self._base_source(spec),
            new_source=self._base_source(spec),
            old_value=old_snapshot,
            new_value=self._snapshot(spec, self._base_value(spec)),
            pending_restart=spec.requires_restart,
            actor=actor,
            client_ip=client_ip,
        )
        OperationLogService(self.base_settings).record(
            session,
            user_id=actor.id,
            action="system_settings.reset",
            target_type="system_settings",
            target_id=None,
            status="success",
            detail=key,
        )
        session.flush()
        return spec

    def list_changes(
        self,
        session: Session,
        *,
        offset: int,
        limit: int,
        setting_key: str | None = None,
        category: str | None = None,
    ) -> tuple[int, list[SystemSettingChange]]:
        statement = select(SystemSettingChange)
        count_statement = select(func.count(SystemSettingChange.id))
        if setting_key:
            statement = statement.where(SystemSettingChange.setting_key == setting_key)
            count_statement = count_statement.where(SystemSettingChange.setting_key == setting_key)
        if category:
            statement = statement.where(SystemSettingChange.category == category)
            count_statement = count_statement.where(SystemSettingChange.category == category)
        total = session.scalar(count_statement) or 0
        items = list(
            session.scalars(
                statement.order_by(SystemSettingChange.created_at.desc(), SystemSettingChange.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return total, items

    def pending_restart_count(self, session: Session) -> int:
        return session.scalar(select(func.count(SystemSetting.id)).where(SystemSetting.pending_restart.is_(True))) or 0

    def database_override_count(self, session: Session) -> int:
        return session.scalar(select(func.count(SystemSetting.id))) or 0

    def clear_pending_restart(self, session: Session) -> None:
        rows = list(session.scalars(select(SystemSetting).where(SystemSetting.pending_restart.is_(True))))
        for row in rows:
            row.pending_restart = False
            spec = SYSTEM_SETTING_REGISTRY.get(row.key)
            if spec is None:
                continue
            session.add(
                SystemSettingChange(
                    setting_key=row.key,
                    category=row.category,
                    action="apply_restart",
                    old_source="database",
                    new_source="database",
                    old_value_snapshot="***" if row.is_secret else str(row.value_json),
                    new_value_snapshot="***" if row.is_secret else str(row.value_json),
                    is_secret=row.is_secret,
                    requires_restart=row.requires_restart,
                    pending_restart_after_change=False,
                )
            )
        session.flush()

    def _build_effective_settings(self, session: Session, *, include_pending: bool) -> Settings:
        updates: dict[str, Any] = {}
        rows = list(session.scalars(select(SystemSetting)))
        for row in rows:
            spec = SYSTEM_SETTING_REGISTRY.get(row.key)
            if spec is None or spec.attr is None or not row.is_valid:
                continue
            if row.pending_restart and row.requires_restart and not include_pending:
                continue
            try:
                updates[spec.attr] = self._row_value(spec, row)
            except Exception as exc:
                row.is_valid = False
                row.invalid_reason = str(exc)
        session.flush()
        return self.base_settings.model_copy(update=updates)

    def _effective_item(self, spec: SettingSpec, row: SystemSetting | None) -> SystemSettingEffectiveItem:
        source = "database" if row else self._base_source(spec)
        configured = bool(row) if spec.editable else bool(self._base_value(spec))
        value = None if spec.secret else (self._row_value(spec, row) if row else self._base_value(spec))
        if spec.key == "DATABASE_URL":
            value = "已配置"
            configured = bool(self.base_settings.database_url)
        if spec.key == "CREDENTIAL_ENCRYPTION_KEY":
            configured = bool(self.base_settings.credential_encryption_key)
        if spec.key == "JWT_SECRET_KEY":
            configured = self.base_settings.jwt_secret_key != "change-me-in-production"
        return SystemSettingEffectiveItem(
            key=spec.key,
            name=spec.name,
            category=spec.category,
            value_type=spec.value_type,
            value=value,
            configured=configured,
            source=source,
            editable=spec.editable,
            secret=spec.secret,
            requires_restart=spec.requires_restart,
            pending_restart=bool(row.pending_restart) if row else False,
            is_valid=bool(row.is_valid) if row else True,
            invalid_reason=row.invalid_reason if row else None,
            updated_at=row.updated_at if row else None,
        )

    def _base_value(self, spec: SettingSpec) -> Any:
        return getattr(self.base_settings, spec.attr) if spec.attr else None

    def _base_source(self, spec: SettingSpec) -> str:
        if spec.attr is None:
            return "system"
        default = Settings()
        return "system" if getattr(self.base_settings, spec.attr) != getattr(default, spec.attr) else "default"

    def _validate_value(self, spec: SettingSpec, raw_value: Any) -> Any:
        if spec.secret and not self.encryption.enabled:
            raise SystemSettingError("未配置 CREDENTIAL_ENCRYPTION_KEY，不能保存敏感配置")
        if spec.value_type == "int":
            try:
                value = int(raw_value)
            except (TypeError, ValueError) as exc:
                raise SystemSettingError(f"{spec.name} 必须是整数") from exc
            if spec.min_value is not None and value < spec.min_value:
                raise SystemSettingError(f"{spec.name} 不能小于 {spec.min_value}")
            if spec.max_value is not None and value > spec.max_value:
                raise SystemSettingError(f"{spec.name} 不能大于 {spec.max_value}")
            return value
        if spec.value_type == "bool":
            if isinstance(raw_value, bool):
                return raw_value
            if isinstance(raw_value, str):
                return raw_value.lower() in {"1", "true", "yes", "on", "启用"}
            return bool(raw_value)
        if spec.value_type == "enum":
            value = str(raw_value)
            if spec.options and value not in spec.options:
                raise SystemSettingError(f"{spec.name} 只能是：{', '.join(spec.options)}")
            return value
        value = "" if raw_value is None else str(raw_value).strip()
        if spec.key in {"REMOTE_GATEWAY_HOST", "DEFAULT_DEVICE_SSH_USER"} and not value:
            raise SystemSettingError(f"{spec.name} 不能为空")
        return value or None

    def _row_value(self, spec: SettingSpec, row: SystemSetting | None) -> Any:
        if row is None:
            return self._base_value(spec)
        if spec.secret:
            return self._decrypt_secret(row.secret_value_encrypted)
        return row.value_json

    def _encrypt_secret(self, value: Any) -> str:
        encrypted = self.encryption.encrypt_optional(str(value))
        if not encrypted or encrypted == value:
            raise SystemSettingError("敏感配置未加密，已拒绝保存")
        return encrypted

    def _decrypt_secret(self, value: str | None) -> str | None:
        return self.encryption.decrypt_optional(value)

    def _snapshot(self, spec: SettingSpec, value: Any) -> str | None:
        if spec.secret:
            return "***" if value else None
        return None if value is None else str(value)

    def _record_change(
        self,
        session: Session,
        *,
        spec: SettingSpec,
        action: str,
        old_source: str | None,
        new_source: str | None,
        old_value: str | None,
        new_value: str | None,
        pending_restart: bool,
        actor: User,
        client_ip: str | None,
    ) -> None:
        session.add(
            SystemSettingChange(
                setting_key=spec.key,
                category=spec.category,
                action=action,
                old_source=old_source,
                new_source=new_source,
                old_value_snapshot=old_value,
                new_value_snapshot=new_value,
                is_secret=spec.secret,
                requires_restart=spec.requires_restart,
                pending_restart_after_change=pending_restart,
                actor_user_id=actor.id,
                actor_username=actor.username,
                client_ip=client_ip,
            )
        )


def schedule_process_exit(delay_seconds: float = 1.0) -> None:
    timer = threading.Timer(delay_seconds, lambda: os._exit(0))
    timer.daemon = True
    timer.start()
