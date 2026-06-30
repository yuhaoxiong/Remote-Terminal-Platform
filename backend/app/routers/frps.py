from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies import request_session, require_admin_user
from app.models.user import User
from app.schemas.frps import FrpsImportRequest, FrpsImportResponse
from app.services.frps_import import FrpsDashboardError, FrpsImportService
from app.services.operation_log import OperationLogService

router = APIRouter(prefix="/frps", tags=["frps"])


@router.post("/discover", response_model=FrpsImportResponse)
def discover_frps_devices(
    payload: FrpsImportRequest,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> FrpsImportResponse:
    with request_session(request) as (settings, session):
        service = FrpsImportService(settings, dashboard_client=getattr(request.app.state, "frps_dashboard_client", None))
        try:
            return service.discover(session, payload)
        except FrpsDashboardError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/import", response_model=FrpsImportResponse)
def import_frps_devices(
    payload: FrpsImportRequest,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> FrpsImportResponse:
    with request_session(request) as (settings, session):
        service = FrpsImportService(settings, dashboard_client=getattr(request.app.state, "frps_dashboard_client", None))
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
