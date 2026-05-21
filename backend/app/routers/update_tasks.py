import csv
import json
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.database import session_scope
from app.dependencies import get_app_settings, get_current_user
from app.models.device import Device
from app.models.user import User
from app.schemas.update_task import (
    UpdateTaskCreate,
    UpdateTaskListResponse,
    UpdateTaskRead,
    UpdateTaskTargetPreviewRequest,
    UpdateTaskTargetPreviewResponse,
)
from app.services.operation_log import OperationLogService
from app.services.update_task_service import (
    UpdateTaskInvalidStateError,
    UpdateTaskNotFoundError,
    UpdateTaskService,
)

router = APIRouter(prefix="/update-tasks", tags=["update-tasks"])

CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def _csv_safe(value: object) -> object:
    if isinstance(value, str) and value.startswith(CSV_FORMULA_PREFIXES):
        return f"\t{value}"
    return value


def _not_found(exc: UpdateTaskNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/preview-targets", response_model=UpdateTaskTargetPreviewResponse)
def preview_update_task_targets(
    payload: UpdateTaskTargetPreviewRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> UpdateTaskTargetPreviewResponse:
    settings = get_app_settings(request)
    service = UpdateTaskService(settings)
    with session_scope(settings) as session:
        preview = service.preview_targets(session, payload.target_filter, execution_mode=payload.execution_mode)
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="update_task.preview_targets",
            target_type="update_task",
            target_id=None,
            status="success",
            detail=json.dumps({"total": preview.total, "warnings": preview.warnings}, ensure_ascii=False),
        )
        return preview


@router.post("", response_model=UpdateTaskRead, status_code=status.HTTP_201_CREATED)
def create_update_task(
    payload: UpdateTaskCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> UpdateTaskRead:
    settings = get_app_settings(request)
    service = UpdateTaskService(settings)
    with session_scope(settings) as session:
        task = service.create(session, payload)
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="update_task.create",
            target_type="update_task",
            target_id=task.id,
            status="success",
            detail=task.name,
        )
        return service.to_read(session, task)


@router.get("", response_model=UpdateTaskListResponse)
def list_update_tasks(
    request: Request,
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = None,
) -> UpdateTaskListResponse:
    settings = get_app_settings(request)
    service = UpdateTaskService(settings)
    with session_scope(settings) as session:
        total, tasks = service.list(session, offset=offset, limit=limit, status=status)
        return UpdateTaskListResponse(total=total, items=[service.to_read(session, task) for task in tasks])


@router.get("/{task_id}", response_model=UpdateTaskRead)
def get_update_task(
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> UpdateTaskRead:
    settings = get_app_settings(request)
    service = UpdateTaskService(settings)
    with session_scope(settings) as session:
        try:
            return service.to_read(session, service.get(session, task_id))
        except UpdateTaskNotFoundError as exc:
            raise _not_found(exc) from exc


@router.post("/{task_id}/execute", response_model=UpdateTaskRead)
def execute_update_task(
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> UpdateTaskRead:
    settings = get_app_settings(request)
    service = UpdateTaskService(settings, ssh_service=getattr(request.app.state, "ssh_service", None))
    with session_scope(settings) as session:
        try:
            task = service.execute(session, task_id)
        except UpdateTaskNotFoundError as exc:
            raise _not_found(exc) from exc
        except UpdateTaskInvalidStateError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="update_task.execute",
            target_type="update_task",
            target_id=task.id,
            status=task.status,
            detail=json.dumps(service.execution_stats(session, task), ensure_ascii=False),
        )
        return service.to_read(session, task)


@router.post("/{task_id}/cancel", response_model=UpdateTaskRead)
def cancel_update_task(
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> UpdateTaskRead:
    settings = get_app_settings(request)
    service = UpdateTaskService(settings)
    with session_scope(settings) as session:
        try:
            task = service.cancel(session, task_id)
        except UpdateTaskNotFoundError as exc:
            raise _not_found(exc) from exc
        except UpdateTaskInvalidStateError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="update_task.cancel",
            target_type="update_task",
            target_id=task.id,
            status=task.status,
            detail=task.name,
        )
        return service.to_read(session, task)


@router.get("/{task_id}/export")
def export_update_task_results(
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Response:
    settings = get_app_settings(request)
    service = UpdateTaskService(settings)
    with session_scope(settings) as session:
        try:
            task = service.get(session, task_id)
            rows = service.device_rows(session, task.id)
        except UpdateTaskNotFoundError as exc:
            raise _not_found(exc) from exc
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "task_id",
                "task_name",
                "device_id",
                "device_sn",
                "status",
                "exit_code",
                "stdout_summary",
                "stderr_summary",
                "error_message",
                "started_at",
                "finished_at",
            ]
        )
        for row in rows:
            device = session.get(Device, row.device_id)
            writer.writerow(
                [
                    _csv_safe(task.id),
                    _csv_safe(task.name),
                    _csv_safe(row.device_id),
                    _csv_safe(device.device_sn if device is not None else ""),
                    _csv_safe(row.status),
                    _csv_safe(row.exit_code),
                    _csv_safe(row.stdout_summary),
                    _csv_safe(row.stderr_summary),
                    _csv_safe(row.error_message),
                    _csv_safe(row.started_at),
                    _csv_safe(row.finished_at),
                ]
            )
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="update_task.export",
            target_type="update_task",
            target_id=task.id,
            status="success",
            detail=task.name,
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="update_task_{task_id}_results.csv"',
            "X-Content-Type-Options": "nosniff",
        },
    )
