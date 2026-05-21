from fastapi import APIRouter, Depends, Request

from app.dependencies import get_app_settings, get_current_user
from app.migrations import migration_status
from app.models.user import User
from app.schemas.diagnostics import (
    DiagnosticsConfigResponse,
    DiagnosticsAuthLifetimeSummary,
    DiagnosticsDatabaseSummary,
    DiagnosticsMigrationSummary,
    DiagnosticsSecuritySummary,
    DiagnosticsSshHostKeySummary,
)

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


def _database_summary(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        return f"sqlite:///{database_url.rsplit('/', 1)[-1]}"
    return database_url.split("://", 1)[0] if "://" in database_url else "configured"


def _security_summary(settings) -> DiagnosticsSecuritySummary:
    warnings: list[str] = []
    jwt_secret_configured = settings.jwt_secret_key != "change-me-in-production"
    default_admin_password_in_use = (
        settings.default_admin_username == "admin" and settings.default_admin_password == "admin"
    )
    default_device_ssh_password_in_use = settings.default_device_ssh_password == "123456"
    credential_encryption_configured = bool(settings.credential_encryption_key)

    if not jwt_secret_configured:
        warnings.append("JWT 密钥仍为默认值，请在部署环境配置 JWT_SECRET_KEY")
    if default_admin_password_in_use:
        warnings.append("管理员账号仍使用默认密码，请修改 DEFAULT_ADMIN_PASSWORD")
    if default_device_ssh_password_in_use:
        warnings.append("设备默认 SSH 密码仍为默认值，请按部署环境调整")
    if not credential_encryption_configured:
        warnings.append("未配置设备凭据加密密钥，新增设备凭据将以兼容模式保存")

    return DiagnosticsSecuritySummary(
        credential_encryption_configured=credential_encryption_configured,
        jwt_secret_configured=jwt_secret_configured,
        default_admin_password_in_use=default_admin_password_in_use,
        default_device_ssh_password_in_use=default_device_ssh_password_in_use,
        warnings=warnings,
    )


def _migration_summary(settings) -> DiagnosticsMigrationSummary:
    status = migration_status(settings)
    return DiagnosticsMigrationSummary(
        current_revision=status.current_revision,
        head_revision=status.head_revision,
        has_pending_migrations=status.has_pending_migrations,
        last_error=status.last_error,
    )


def _ssh_host_key_summary(settings) -> DiagnosticsSshHostKeySummary:
    warnings: list[str] = []
    if settings.ssh_host_key_policy == "auto_add":
        warnings.append("SSH 主机密钥策略为 auto_add，生产环境建议配置 known_hosts 并使用 warning 或 reject")
    if settings.ssh_host_key_policy in {"warning", "reject"} and not settings.ssh_known_hosts_file:
        warnings.append("SSH 主机密钥策略需要 known_hosts 文件，但当前未配置 SSH_KNOWN_HOSTS_FILE")
    return DiagnosticsSshHostKeySummary(
        policy=settings.ssh_host_key_policy,
        known_hosts_configured=bool(settings.ssh_known_hosts_file),
        warnings=warnings,
    )


@router.get("/config", response_model=DiagnosticsConfigResponse)
def get_diagnostics_config(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> DiagnosticsConfigResponse:
    settings = get_app_settings(request)
    return DiagnosticsConfigResponse(
        service_name=settings.service_name,
        version=settings.version,
        api_prefix=settings.api_prefix,
        database=_database_summary(settings.database_url),
        file_backend=settings.file_backend,
        remote_gateway_host=settings.remote_gateway_host,
        vnc_gateway_host=settings.vnc_gateway_host or settings.remote_gateway_host,
        ssh_timeout_seconds=settings.ssh_timeout_seconds,
        vnc_timeout_seconds=settings.vnc_timeout_seconds,
        default_device_ssh_user=settings.default_device_ssh_user,
        security=_security_summary(settings),
        migration=_migration_summary(settings),
        ssh_host_key=_ssh_host_key_summary(settings),
        auth_lifetime=DiagnosticsAuthLifetimeSummary(
            access_expire_minutes=settings.access_token_expire_minutes,
            refresh_expire_minutes=settings.refresh_token_expire_minutes,
            jwt_secret_configured=settings.jwt_secret_key != "change-me-in-production",
        ),
        database_status=DiagnosticsDatabaseSummary(
            summary=_database_summary(settings.database_url),
            sqlite_backup_recommended=settings.database_url.startswith("sqlite"),
        ),
    )
