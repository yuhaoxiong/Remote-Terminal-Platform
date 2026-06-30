from collections.abc import Callable, Iterator
from contextlib import contextmanager

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import session_scope
from app.enums import UserRole
from app.models.user import User
from app.services.operation_log import OperationLogService
from app.services.security import TokenError, decode_token, token_matches_password_version

bearer_scheme = HTTPBearer()


def get_app_settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", get_settings())


@contextmanager
def request_session(request: Request) -> Iterator[tuple[Settings, Session]]:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        yield settings, session


def not_found_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def conflict_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> User:
    settings = get_app_settings(request)
    try:
        payload = decode_token(settings, credentials.credentials, "access")
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    username = str(payload.get("sub", ""))
    with session_scope(settings) as session:
        user = session.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        if not token_matches_password_version(payload, user.password_changed_at):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        session.expunge(user)
        return user


def _forbidden(request: Request, settings: Settings, user: User, required_roles: set[str]) -> HTTPException:
    with session_scope(settings) as session:
        OperationLogService(settings).record(
            session,
            user_id=user.id,
            action="auth.forbidden",
            target_type="permission",
            target_id=None,
            status="failed",
            detail=f"{request.url.path}: required={','.join(sorted(required_roles))}, actual={user.role}",
        )
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号无权限执行该操作")


def ensure_roles(user: User, roles: set[UserRole | str], request: Request, settings: Settings) -> None:
    required_roles = {role.value if isinstance(role, UserRole) else role for role in roles}
    if user.role not in required_roles:
        raise _forbidden(request, settings, user, required_roles)


def ensure_admin(user: User, request: Request, settings: Settings) -> None:
    ensure_roles(user, {UserRole.admin}, request, settings)


def require_roles(roles: set[UserRole | str]) -> Callable[[Request, User], User]:
    def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> User:
        ensure_roles(current_user, roles, request, get_app_settings(request))
        return current_user

    return dependency


def require_admin_user(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    ensure_admin(current_user, request, get_app_settings(request))
    return current_user
