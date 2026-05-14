from fastapi import APIRouter, Depends, Request

from app.dependencies import get_app_settings, get_current_user
from app.models.user import User
from app.schemas.diagnostics import DiagnosticsConfigResponse

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


def _database_summary(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        return f"sqlite:///{database_url.rsplit('/', 1)[-1]}"
    return database_url.split("://", 1)[0] if "://" in database_url else "configured"


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
    )
