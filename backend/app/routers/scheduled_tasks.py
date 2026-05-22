from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.dependencies import get_current_user, not_found_error, request_session
from app.models.user import User
from app.schemas.log import OperationLogListResponse, OperationLogRead
from app.schemas.scheduled_task import (
    ScheduledTaskCreate,
    ScheduledTaskExecuteResponse,
    ScheduledTaskListResponse,
    ScheduledTaskRead,
    ScheduledTaskRunListResponse,
    ScheduledTaskRunRead,
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
            run = ScheduledTaskService(settings).run_now(session, task_id, user_id=current_user.id, trigger_type="manual")
        except ScheduledTaskNotFoundError as exc:
            raise not_found_error(exc) from exc
        return ScheduledTaskExecuteResponse(
            task_id=task_id,
            status=run.status,
            output_summary=run.output_summary or run.error_message or run.status,
            run_id=run.id,
        )


@router.post("/{task_id}/run-now", response_model=ScheduledTaskExecuteResponse)
def run_scheduled_task_now(
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> ScheduledTaskExecuteResponse:
    return execute_scheduled_task(task_id, request, current_user)


@router.get("/{task_id}/runs", response_model=ScheduledTaskRunListResponse)
def scheduled_task_runs(
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ScheduledTaskRunListResponse:
    with request_session(request) as (settings, session):
        try:
            total, runs = ScheduledTaskService(settings).list_runs(session, task_id, offset=offset, limit=limit)
        except ScheduledTaskNotFoundError as exc:
            raise not_found_error(exc) from exc
        return ScheduledTaskRunListResponse(total=total, items=[ScheduledTaskRunRead.model_validate(run) for run in runs])


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
