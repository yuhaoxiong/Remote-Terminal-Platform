from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.dependencies import conflict_error, get_current_user, not_found_error, request_session, require_admin_user
from app.models.user import User
from app.schemas.group import GroupCreate, GroupListResponse, GroupRead, GroupUpdate
from app.services.group_service import GroupDuplicateError, GroupNotFoundError, GroupService
from app.services.operation_log import OperationLogService

router = APIRouter(prefix="/groups", tags=["groups"])


def _read(group) -> GroupRead:
    return GroupRead.model_validate(group)


@router.post("", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> GroupRead:
    with request_session(request) as (settings, session):
        try:
            group = GroupService(settings).create(session, payload)
        except GroupDuplicateError as exc:
            raise conflict_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="group.create",
            target_type="group",
            target_id=group.id,
            status="success",
            detail=group.name,
        )
        return _read(group)


@router.get("", response_model=GroupListResponse)
def list_groups(
    request: Request,
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> GroupListResponse:
    with request_session(request) as (settings, session):
        total, groups = GroupService(settings).list(session, offset=offset, limit=limit)
        return GroupListResponse(total=total, items=[_read(group) for group in groups])


@router.put("/{group_id}", response_model=GroupRead)
def update_group(
    group_id: int,
    payload: GroupUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> GroupRead:
    with request_session(request) as (settings, session):
        try:
            group = GroupService(settings).update(session, group_id, payload)
        except GroupNotFoundError as exc:
            raise not_found_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="group.update",
            target_type="group",
            target_id=group.id,
            status="success",
            detail=group.name,
        )
        return _read(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> Response:
    with request_session(request) as (settings, session):
        try:
            group = GroupService(settings).get(session, group_id)
            name = group.name
            GroupService(settings).delete(session, group_id)
        except GroupNotFoundError as exc:
            raise not_found_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="group.delete",
            target_type="group",
            target_id=group_id,
            status="success",
            detail=name,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
