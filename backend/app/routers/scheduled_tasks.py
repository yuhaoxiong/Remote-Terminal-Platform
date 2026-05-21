from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.dependencies import get_current_user, not_found_error, request_session
from app.models.user import User
from app.schemas.log import OperationLogListResponse, OperationLogRead
from app.schemas.scheduled_task import (
    ScheduledTaskCreate,
    ScheduledTaskExecuteResponse,
    ScheduledTaskListResponse,
    ScheduledTaskRead,
    ScheduledTaskUpdate,
)
from app.services.operation_log import OperationLogService
from app.services.scheduled_task_service import ScheduledTaskNotFoundError, ScheduledTaskService

router = APIRouter(prefix="/scheduled-tasks", tags=["scheduled-tasks"])


@router.post("", response_model=ScheduledTaskRead, status_code=status.HTTP_201_CREATED)
def create_scheduled_task(
    payload: ScheduledTaskCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> ScheduledTaskRead:
    with request_session(request) as (settings, session):
        task = ScheduledTaskService(settings).create(session, payload)
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="scheduled_task.create",
            target_type="scheduled_task",
            target_id=task.id,
            status="success",
            detail=task.name,
        )
        return ScheduledTaskRead.model_validate(task)


@router.get("", response_model=ScheduledTaskListResponse)
def list_scheduled_tasks(
    request: Request,
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ScheduledTaskListResponse:
    with request_session(request) as (settings, session):
        total, tasks = ScheduledTaskService(settings).list(session, offset=offset, limit=limit)
        return ScheduledTaskListResponse(total=total, items=[ScheduledTaskRead.model_validate(task) for task in tasks])


@router.put("/{task_id}", response_model=ScheduledTaskRead)
def update_scheduled_task(
    task_id: int,
    payload: ScheduledTaskUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> ScheduledTaskRead:
    with request_session(request) as (settings, session):
        try:
            task = ScheduledTaskService(settings).update(session, task_id, payload)
        except ScheduledTaskNotFoundError as exc:
            raise not_found_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="scheduled_task.update",
            target_type="scheduled_task",
            target_id=task.id,
            status="success",
            detail=task.name,
        )
        return ScheduledTaskRead.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scheduled_task(
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Response:
    with request_session(request) as (settings, session):
        try:
            task = ScheduledTaskService(settings).get(session, task_id)
            name = task.name
            ScheduledTaskService(settings).delete(session, task_id)
        except ScheduledTaskNotFoundError as exc:
            raise not_found_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="scheduled_task.delete",
            target_type="scheduled_task",
            target_id=task_id,
            status="success",
            detail=name,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{task_id}/toggle", response_model=ScheduledTaskRead)
def toggle_scheduled_task(
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> ScheduledTaskRead:
    with request_session(request) as (settings, session):
        try:
            task = ScheduledTaskService(settings).toggle(session, task_id)
        except ScheduledTaskNotFoundError as exc:
            raise not_found_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="scheduled_task.toggle",
            target_type="scheduled_task",
            target_id=task.id,
            status="success",
            detail=f"enabled={task.enabled}",
        )
        return ScheduledTaskRead.model_validate(task)


@router.post("/{task_id}/execute", response_model=ScheduledTaskExecuteResponse)
def execute_scheduled_task(
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> ScheduledTaskExecuteResponse:
    with request_session(request) as (settings, session):
        try:
            summary = ScheduledTaskService(settings).execute(session, task_id, user_id=current_user.id)
        except ScheduledTaskNotFoundError as exc:
            raise not_found_error(exc) from exc
        return ScheduledTaskExecuteResponse(task_id=task_id, status="success", output_summary=summary)


@router.get("/{task_id}/logs", response_model=OperationLogListResponse)
def scheduled_task_logs(
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> OperationLogListResponse:
    with request_session(request) as (settings, session):
        try:
            total, logs = ScheduledTaskService(settings).logs(session, task_id)
        except ScheduledTaskNotFoundError as exc:
            raise not_found_error(exc) from exc
        return OperationLogListResponse(total=total, items=[OperationLogRead.model_validate(log) for log in logs])
