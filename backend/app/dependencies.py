from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.config import Settings, get_settings
from app.database import session_scope
from app.models.user import User
from app.services.security import TokenError, decode_token

bearer_scheme = HTTPBearer()


def get_app_settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", get_settings())


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
        session.expunge(user)
        return user
