from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.group import Group
from app.schemas.group import GroupCreate, GroupUpdate


class GroupDuplicateError(RuntimeError):
    pass


class GroupNotFoundError(RuntimeError):
    pass


class GroupService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self, session: Session, payload: GroupCreate) -> Group:
        existing_id = session.scalar(select(Group.id).where(Group.name == payload.name))
        if existing_id is not None:
            raise GroupDuplicateError(f"Group already exists: {payload.name}")
        group = Group(**payload.model_dump())
        session.add(group)
        session.flush()
        session.refresh(group)
        return group

    def list(self, session: Session, *, offset: int, limit: int) -> tuple[int, list[Group]]:
        total = session.scalar(select(func.count(Group.id))) or 0
        groups = list(session.scalars(select(Group).order_by(Group.id.asc()).offset(offset).limit(limit)))
        return total, groups

    def get(self, session: Session, group_id: int) -> Group:
        group = session.get(Group, group_id)
        if group is None:
            raise GroupNotFoundError(f"Group not found: {group_id}")
        return group

    def update(self, session: Session, group_id: int, payload: GroupUpdate) -> Group:
        group = self.get(session, group_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(group, field, value)
        session.flush()
        session.refresh(group)
        return group

    def delete(self, session: Session, group_id: int) -> None:
        group = self.get(session, group_id)
        session.delete(group)
        session.flush()
