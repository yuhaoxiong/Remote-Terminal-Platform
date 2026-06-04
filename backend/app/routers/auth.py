from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select

from app.config import Settings
from app.dependencies import get_current_user, request_session
from app.models.user import User
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    PasswordChangeRequest,
    RefreshRequest,
    TokenResponse,
)
from app.services.security import (
    TokenError,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.services.operation_log import OperationLogService

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(settings: Settings, username: str) -> TokenResponse:
    access_token = create_token(
        settings,
        subject=username,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token = create_token(
        settings,
        subject=username,
        token_type="refresh",
        expires_delta=timedelta(minutes=settings.refresh_token_expire_minutes),
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request) -> TokenResponse:
    with request_session(request) as (settings, session):
        user = session.scalar(select(User).where(User.username == payload.username))
        if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
            OperationLogService(settings).record(
                session,
                user_id=user.id if user is not None else None,
                action="auth.login",
                target_type="user",
                target_id=user.id if user is not None else None,
                status="failed",
                detail=f"username={payload.username}, ip={_client_ip(request) or ''}",
            )
            session.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
        user.last_login_at = datetime.now(timezone.utc)
        user.last_login_ip = _client_ip(request)
        OperationLogService(settings).record(
            session,
            user_id=user.id,
            action="auth.login",
            target_type="user",
            target_id=user.id,
            status="success",
            detail=f"ip={user.last_login_ip or ''}",
        )
        return _issue_tokens(settings, user.username)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, request: Request) -> TokenResponse:
    with request_session(request) as (settings, session):
        try:
            token_payload = decode_token(settings, payload.refresh_token, "refresh")
        except TokenError as exc:
            OperationLogService(settings).record(
                session,
                user_id=None,
                action="auth.refresh",
                target_type="user",
                target_id=None,
                status="failed",
                detail=f"invalid token, ip={_client_ip(request) or ''}",
            )
            session.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

        username = str(token_payload.get("sub", ""))
        user = session.scalar(select(User).where(User.username == username))
        if user is None or not user.is_active:
            OperationLogService(settings).record(
                session,
                user_id=user.id if user is not None else None,
                action="auth.refresh",
                target_type="user",
                target_id=user.id if user is not None else None,
                status="failed",
                detail=f"username={username}, ip={_client_ip(request) or ''}",
            )
            session.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        OperationLogService(settings).record(
            session,
            user_id=user.id,
            action="auth.refresh",
            target_type="user",
            target_id=user.id,
            status="success",
            detail=f"ip={_client_ip(request) or ''}",
        )
        return _issue_tokens(settings, user.username)


@router.get("/me", response_model=CurrentUserResponse)
def me(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        is_active=current_user.is_active,
    )


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Response:
    with request_session(request) as (_settings, session):
        user = session.get(User, current_user.id)
        if user is None or not verify_password(payload.old_password, user.password_hash):
            OperationLogService(_settings).record(
                session,
                user_id=current_user.id,
                action="auth.password_change",
                target_type="user",
                target_id=current_user.id,
                status="failed",
                detail="旧密码错误",
            )
            session.commit()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is incorrect")
        user.password_hash = hash_password(payload.new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        OperationLogService(_settings).record(
            session,
            user_id=current_user.id,
            action="auth.password_change",
            target_type="user",
            target_id=current_user.id,
            status="success",
            detail="密码已修改",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
