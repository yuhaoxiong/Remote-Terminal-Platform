from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.config import Settings
from app.models.log import OperationLog


class OperationLogService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def record(
        self,
        session: Session,
        *,
        user_id: int | None,
        action: str,
        target_type: str | None,
        target_id: int | None,
        status: str,
        detail: str | None = None,
    ) -> OperationLog:
        log = OperationLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            status=status,
            detail=detail,
        )
        session.add(log)
        session.flush()
        return log

    def list(
        self,
        session: Session,
        *,
        offset: int,
        limit: int,
        action: str | None = None,
        target_type: str | None = None,
        status: str | None = None,
    ) -> tuple[int, list[OperationLog]]:
        statement = select(OperationLog)
        count_statement = select(func.count(OperationLog.id))
        if action:
            statement = statement.where(OperationLog.action == action)
            count_statement = count_statement.where(OperationLog.action == action)
        if target_type:
            statement = statement.where(OperationLog.target_type == target_type)
            count_statement = count_statement.where(OperationLog.target_type == target_type)
        if status:
            statement = statement.where(OperationLog.status == status)
            count_statement = count_statement.where(OperationLog.status == status)

        total = session.scalar(count_statement) or 0
        logs = list(
            session.scalars(
                statement.order_by(OperationLog.created_at.desc(), OperationLog.id.desc()).offset(offset).limit(limit)
            )
        )
        return total, logs
