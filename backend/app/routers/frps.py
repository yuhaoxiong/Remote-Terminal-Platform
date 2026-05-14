from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.database import session_scope
from app.dependencies import get_app_settings, get_current_user
from app.models.user import User
from app.schemas.frps import FrpsImportRequest, FrpsImportResponse
from app.services.frps_import import FrpsDashboardError, FrpsImportService
from app.services.operation_log import OperationLogService

router = APIRouter(prefix="/frps", tags=["frps"])


@router.post("/discover", response_model=FrpsImportResponse)
def discover_frps_devices(
    payload: FrpsImportRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> FrpsImportResponse:
    settings = get_app_settings(request)
    service = FrpsImportService(settings, dashboard_client=getattr(request.app.state, "frps_dashboard_client", None))
    with session_scope(settings) as session:
        try:
            return service.discover(session, payload)
        except FrpsDashboardError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/import", response_model=FrpsImportResponse)
def import_frps_devices(
    payload: FrpsImportRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> FrpsImportResponse:
    settings = get_app_settings(request)
    service = FrpsImportService(settings, dashboard_client=getattr(request.app.state, "frps_dashboard_client", None))
    with session_scope(settings) as session:
        try:
            result = service.import_devices(session, payload)
        except FrpsDashboardError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="frps.import",
            target_type="frps",
            target_id=None,
            status="success",
            detail=f"created={result.created}, synced={result.synced}, skipped={result.skipped}, conflicts={result.conflicts}",
        )
        return result
