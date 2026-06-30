from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.config import Settings


class TokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def password_version(password_changed_at: datetime | None) -> str:
    if password_changed_at is None:
        return ""
    if password_changed_at.tzinfo is None:
        password_changed_at = password_changed_at.replace(tzinfo=timezone.utc)
    else:
        password_changed_at = password_changed_at.astimezone(timezone.utc)
    return password_changed_at.isoformat(timespec="microseconds")


def token_matches_password_version(payload: dict[str, Any], password_changed_at: datetime | None) -> bool:
    return str(payload.get("pwd", "")) == password_version(password_changed_at)


def create_token(
    settings: Settings,
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    password_changed_at: datetime | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "pwd": password_version(password_changed_at),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(settings: Settings, token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid token") from exc
    if payload.get("type") != expected_type:
        raise TokenError("Invalid token type")
    return payload
