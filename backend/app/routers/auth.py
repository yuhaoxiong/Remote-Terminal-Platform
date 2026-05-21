from datetime import timedelta

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


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request) -> TokenResponse:
    with request_session(request) as (settings, session):
        user = session.scalar(select(User).where(User.username == payload.username, User.is_active.is_(True)))
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
        return _issue_tokens(settings, user.username)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, request: Request) -> TokenResponse:
    with request_session(request) as (settings, session):
        try:
            token_payload = decode_token(settings, payload.refresh_token, "refresh")
        except TokenError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

        username = str(token_payload.get("sub", ""))
        user = session.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        return _issue_tokens(settings, user.username)


@router.get("/me", response_model=CurrentUserResponse)
def me(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(id=current_user.id, username=current_user.username)


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Response:
    with request_session(request) as (_settings, session):
        user = session.get(User, current_user.id)
        if user is None or not verify_password(payload.old_password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is incorrect")
        user.password_hash = hash_password(payload.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
