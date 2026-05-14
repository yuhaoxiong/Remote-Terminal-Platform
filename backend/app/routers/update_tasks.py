from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.database import session_scope
from app.dependencies import get_app_settings, get_current_user
from app.models.user import User
from app.schemas.update_task import UpdateTaskCreate, UpdateTaskListResponse, UpdateTaskRead
from app.services.operation_log import OperationLogService
from app.services.update_task_service import (
    UpdateTaskInvalidStateError,
    UpdateTaskNotFoundError,
    UpdateTaskService,
)

router = APIRouter(prefix="/update-tasks", tags=["update-tasks"])


def _not_found(exc: UpdateTaskNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


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
    service = UpdateTaskService(settings)
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
            detail=task.name,
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
