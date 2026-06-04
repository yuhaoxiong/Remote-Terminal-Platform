from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import UserRole
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.security import hash_password


class UserNotFoundError(ValueError):
    pass


class UserConflictError(RuntimeError):
    pass


class LastAdminError(RuntimeError):
    pass


class UserService:
    def list(self, session: Session, *, offset: int, limit: int) -> tuple[int, list[User]]:
        total = session.scalar(select(func.count(User.id))) or 0
        users = list(session.scalars(select(User).order_by(User.id.asc()).offset(offset).limit(limit)))
        return total, users

    def get(self, session: Session, user_id: int) -> User:
        user = session.get(User, user_id)
        if user is None:
            raise UserNotFoundError("用户不存在")
        return user

    def create(self, session: Session, payload: UserCreate) -> User:
        existing = session.scalar(select(User).where(User.username == payload.username))
        if existing is not None:
            raise UserConflictError("用户名已存在")
        user = User(
            username=payload.username,
            password_hash=hash_password(payload.password),
            role=payload.role.value,
            is_active=payload.is_active,
            password_changed_at=datetime.now(timezone.utc),
        )
        session.add(user)
        session.flush()
        session.refresh(user)
        return user

    def update(self, session: Session, user_id: int, payload: UserUpdate) -> User:
        user = self.get(session, user_id)
        if payload.role is not None and user.role == UserRole.admin.value and payload.role != UserRole.admin:
            self._ensure_not_last_active_admin(session, user)
            user.role = payload.role.value
        elif payload.role is not None:
            user.role = payload.role.value
        if payload.is_active is not None:
            if user.is_active and not payload.is_active:
                self._ensure_not_last_active_admin(session, user)
            user.is_active = payload.is_active
        session.flush()
        session.refresh(user)
        return user

    def reset_password(self, session: Session, user_id: int, new_password: str) -> User:
        user = self.get(session, user_id)
        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        session.flush()
        session.refresh(user)
        return user

    def set_active(self, session: Session, user_id: int, is_active: bool) -> User:
        return self.update(session, user_id, UserUpdate(is_active=is_active))

    def disable(self, session: Session, user_id: int) -> User:
        return self.set_active(session, user_id, False)

    def _ensure_not_last_active_admin(self, session: Session, user: User) -> None:
        if user.role != UserRole.admin.value or not user.is_active:
            return
        active_admin_count = session.scalar(
            select(func.count(User.id)).where(User.role == UserRole.admin.value, User.is_active.is_(True))
        ) or 0
        if active_admin_count <= 1:
            raise LastAdminError("不能停用或降级最后一个启用的管理员")
