from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.dependencies import conflict_error, not_found_error, request_session, require_admin_user
from app.models.user import User
from app.schemas.user import UserCreate, UserListResponse, UserRead, UserResetPasswordRequest, UserToggleRequest, UserUpdate
from app.services.operation_log import OperationLogService
from app.services.user_service import LastAdminError, UserConflictError, UserNotFoundError, UserService

router = APIRouter(prefix="/users", tags=["users"])


def _read(user: User) -> UserRead:
    return UserRead.model_validate(user)


def _conflict(exc: Exception):
    return conflict_error(exc)


@router.get("", response_model=UserListResponse)
def list_users(
    request: Request,
    current_user: User = Depends(require_admin_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> UserListResponse:
    with request_session(request) as (_settings, session):
        total, users = UserService().list(session, offset=offset, limit=limit)
        return UserListResponse(total=total, items=[_read(user) for user in users])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> UserRead:
    with request_session(request) as (settings, session):
        try:
            user = UserService().create(session, payload)
        except UserConflictError as exc:
            raise _conflict(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="user.create",
            target_type="user",
            target_id=user.id,
            status="success",
            detail=f"{user.username}:{user.role}",
        )
        return _read(user)


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> UserRead:
    with request_session(request) as (_settings, session):
        try:
            return _read(UserService().get(session, user_id))
        except UserNotFoundError as exc:
            raise not_found_error(exc) from exc


@router.put("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> UserRead:
    with request_session(request) as (settings, session):
        try:
            user = UserService().update(session, user_id, payload)
        except UserNotFoundError as exc:
            raise not_found_error(exc) from exc
        except LastAdminError as exc:
            raise _conflict(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="user.update",
            target_type="user",
            target_id=user.id,
            status="success",
            detail=f"role={user.role}, active={user.is_active}",
        )
        return _read(user)


@router.post("/{user_id}/reset-password", response_model=UserRead)
def reset_user_password(
    user_id: int,
    payload: UserResetPasswordRequest,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> UserRead:
    with request_session(request) as (settings, session):
        try:
            user = UserService().reset_password(session, user_id, payload.new_password)
        except UserNotFoundError as exc:
            raise not_found_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="user.reset_password",
            target_type="user",
            target_id=user.id,
            status="success",
            detail=user.username,
        )
        return _read(user)


@router.post("/{user_id}/toggle", response_model=UserRead)
def toggle_user(
    user_id: int,
    payload: UserToggleRequest,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> UserRead:
    with request_session(request) as (settings, session):
        try:
            user = UserService().set_active(session, user_id, payload.is_active)
        except UserNotFoundError as exc:
            raise not_found_error(exc) from exc
        except LastAdminError as exc:
            raise _conflict(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="user.toggle",
            target_type="user",
            target_id=user.id,
            status="success",
            detail=f"active={user.is_active}",
        )
        return _read(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> Response:
    with request_session(request) as (settings, session):
        try:
            user = UserService().disable(session, user_id)
        except UserNotFoundError as exc:
            raise not_found_error(exc) from exc
        except LastAdminError as exc:
            raise _conflict(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="user.disable",
            target_type="user",
            target_id=user.id,
            status="success",
            detail=user.username,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
