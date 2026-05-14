import csv
from io import StringIO

from fastapi import APIRouter, Depends, Query, Request, Response

from app.database import session_scope
from app.dependencies import get_app_settings, get_current_user
from app.models.user import User
from app.schemas.log import OperationLogListResponse, OperationLogRead
from app.services.operation_log import OperationLogService

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=OperationLogListResponse)
def list_logs(
    request: Request,
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = None,
    target_type: str | None = None,
    status: str | None = None,
) -> OperationLogListResponse:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        total, logs = OperationLogService(settings).list(
            session,
            offset=offset,
            limit=limit,
            action=action,
            target_type=target_type,
            status=status,
        )
        return OperationLogListResponse(total=total, items=[OperationLogRead.model_validate(log) for log in logs])


@router.get("/export")
def export_logs(
    request: Request,
    current_user: User = Depends(get_current_user),
    action: str | None = None,
    target_type: str | None = None,
    status: str | None = None,
) -> Response:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        _total, logs = OperationLogService(settings).list(
            session,
            offset=0,
            limit=1000,
            action=action,
            target_type=target_type,
            status=status,
        )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "user_id", "action", "target_type", "target_id", "status", "detail", "created_at"])
    for log in logs:
        writer.writerow(
            [log.id, log.user_id, log.action, log.target_type, log.target_id, log.status, log.detail, log.created_at]
        )
    return Response(content=output.getvalue(), media_type="text/csv")
