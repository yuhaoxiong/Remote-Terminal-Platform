from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.log import OperationLog
from app.models.scheduled_task import ScheduledTask
from app.schemas.scheduled_task import ScheduledTaskCreate, ScheduledTaskUpdate
from app.services.operation_log import OperationLogService


class ScheduledTaskNotFoundError(RuntimeError):
    pass


class ScheduledTaskService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self, session: Session, payload: ScheduledTaskCreate) -> ScheduledTask:
        task = ScheduledTask(**payload.model_dump())
        session.add(task)
        session.flush()
        session.refresh(task)
        return task

    def list(self, session: Session, *, offset: int, limit: int) -> tuple[int, list[ScheduledTask]]:
        total = session.scalar(select(func.count(ScheduledTask.id))) or 0
        tasks = list(session.scalars(select(ScheduledTask).order_by(ScheduledTask.id.asc()).offset(offset).limit(limit)))
        return total, tasks

    def get(self, session: Session, task_id: int) -> ScheduledTask:
        task = session.get(ScheduledTask, task_id)
        if task is None:
            raise ScheduledTaskNotFoundError(f"Scheduled task not found: {task_id}")
        return task

    def update(self, session: Session, task_id: int, payload: ScheduledTaskUpdate) -> ScheduledTask:
        task = self.get(session, task_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(task, field, value)
        session.flush()
        session.refresh(task)
        return task

    def delete(self, session: Session, task_id: int) -> None:
        task = self.get(session, task_id)
        session.delete(task)
        session.flush()

    def toggle(self, session: Session, task_id: int) -> ScheduledTask:
        task = self.get(session, task_id)
        task.enabled = not task.enabled
        session.flush()
        session.refresh(task)
        return task

    def execute(self, session: Session, task_id: int, *, user_id: int | None) -> str:
        task = self.get(session, task_id)
        summary = f"simulated scheduled task execution: {task.command or task.task_type}"
        OperationLogService(self.settings).record(
            session,
            user_id=user_id,
            action="scheduled_task.execute",
            target_type="scheduled_task",
            target_id=task.id,
            status="success",
            detail=summary,
        )
        return summary

    def logs(self, session: Session, task_id: int) -> tuple[int, list[OperationLog]]:
        self.get(session, task_id)
        statement = (
            select(OperationLog)
            .where(OperationLog.target_type == "scheduled_task", OperationLog.target_id == task_id)
            .order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
        )
        logs = list(session.scalars(statement))
        return len(logs), logs
