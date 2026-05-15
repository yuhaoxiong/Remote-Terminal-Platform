from fastapi import APIRouter, Depends, Request

from app.dependencies import get_app_settings, get_current_user
from app.models.user import User
from app.schemas.diagnostics import DiagnosticsConfigResponse, DiagnosticsSecuritySummary

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
    )
