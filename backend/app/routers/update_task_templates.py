from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.database import session_scope
from app.dependencies import get_app_settings, get_current_user
from app.models.user import User
from app.schemas.update_task import (
    UpdateTaskTemplateCreate,
    UpdateTaskTemplateListResponse,
    UpdateTaskTemplateRead,
    UpdateTaskTemplateUpdate,
)
from app.services.operation_log import OperationLogService
from app.services.update_task_service import UpdateTaskService, UpdateTaskTemplateNotFoundError

router = APIRouter(prefix="/update-task-templates", tags=["update-task-templates"])


def _not_found(exc: UpdateTaskTemplateNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("", response_model=UpdateTaskTemplateListResponse)
def list_update_task_templates(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> UpdateTaskTemplateListResponse:
    settings = get_app_settings(request)
    service = UpdateTaskService(settings)
    with session_scope(settings) as session:
        total, templates = service.list_templates(session)
        return UpdateTaskTemplateListResponse(total=total, items=[UpdateTaskTemplateRead.model_validate(item) for item in templates])


@router.post("", response_model=UpdateTaskTemplateRead, status_code=status.HTTP_201_CREATED)
def create_update_task_template(
    payload: UpdateTaskTemplateCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> UpdateTaskTemplateRead:
    settings = get_app_settings(request)
    service = UpdateTaskService(settings)
    with session_scope(settings) as session:
        template = service.create_template(session, payload)
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="update_task_template.create",
            target_type="update_task_template",
            target_id=template.id,
            status="success",
            detail=template.name,
        )
        return UpdateTaskTemplateRead.model_validate(template)


@router.put("/{template_id}", response_model=UpdateTaskTemplateRead)
def update_update_task_template(
    template_id: int,
    payload: UpdateTaskTemplateUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> UpdateTaskTemplateRead:
    settings = get_app_settings(request)
    service = UpdateTaskService(settings)
    with session_scope(settings) as session:
        try:
            template = service.update_template(session, template_id, payload)
        except UpdateTaskTemplateNotFoundError as exc:
            raise _not_found(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="update_task_template.update",
            target_type="update_task_template",
            target_id=template.id,
            status="success",
            detail=template.name,
        )
        return UpdateTaskTemplateRead.model_validate(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_update_task_template(
    template_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Response:
    settings = get_app_settings(request)
    service = UpdateTaskService(settings)
    with session_scope(settings) as session:
        try:
            template = service.get_template(session, template_id)
            name = template.name
            service.delete_template(session, template_id)
        except UpdateTaskTemplateNotFoundError as exc:
            raise _not_found(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="update_task_template.delete",
            target_type="update_task_template",
            target_id=template_id,
            status="success",
            detail=name,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
