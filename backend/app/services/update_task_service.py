from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.device import Device
from app.models.update_task import UpdateTask, UpdateTaskDevice
from app.schemas.update_task import UpdateTaskCreate, UpdateTaskRead


class UpdateTaskNotFoundError(RuntimeError):
    pass


class UpdateTaskInvalidStateError(RuntimeError):
    pass


class UpdateTaskService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self, session: Session, payload: UpdateTaskCreate) -> UpdateTask:
        task = UpdateTask(**payload.model_dump())
        session.add(task)
        session.flush()
        for device in self._target_devices(session, payload.target_filter):
            session.add(UpdateTaskDevice(task_id=task.id, device_id=device.id, status="pending"))
        session.flush()
        session.refresh(task)
        return task

    def list(
        self,
        session: Session,
        *,
        offset: int,
        limit: int,
        status: str | None = None,
    ) -> tuple[int, list[UpdateTask]]:
        statement = select(UpdateTask)
        count_statement = select(func.count(UpdateTask.id))
        if status:
            statement = statement.where(UpdateTask.status == status)
            count_statement = count_statement.where(UpdateTask.status == status)
        total = session.scalar(count_statement) or 0
        tasks = list(session.scalars(statement.order_by(UpdateTask.id.asc()).offset(offset).limit(limit)))
        return total, tasks

    def get(self, session: Session, task_id: int) -> UpdateTask:
        task = session.get(UpdateTask, task_id)
        if task is None:
            raise UpdateTaskNotFoundError(f"Update task not found: {task_id}")
        return task

    def execute(self, session: Session, task_id: int) -> UpdateTask:
        task = self.get(session, task_id)
        if task.status in {"completed", "canceled"}:
            raise UpdateTaskInvalidStateError(f"Update task cannot execute from status: {task.status}")
        task.status = "running"
        now = datetime.now(timezone.utc)
        rows = self.device_rows(session, task.id)
        for row in rows:
            if row.status != "pending":
                continue
            row.status = "success"
            row.started_at = now
            row.finished_at = datetime.now(timezone.utc)
            row.output_summary = f"simulated command execution: {task.command}"
        task.status = "completed" if all(row.status == "success" for row in rows) else "partial_failed"
        session.flush()
        session.refresh(task)
        return task

    def cancel(self, session: Session, task_id: int) -> UpdateTask:
        task = self.get(session, task_id)
        if task.status == "completed":
            raise UpdateTaskInvalidStateError("Completed update task cannot be canceled")
        for row in self.device_rows(session, task.id):
            if row.status in {"pending", "running"}:
                row.status = "canceled"
                row.finished_at = datetime.now(timezone.utc)
        task.status = "canceled"
        session.flush()
        session.refresh(task)
        return task

    def device_rows(self, session: Session, task_id: int) -> list[UpdateTaskDevice]:
        return list(
            session.scalars(
                select(UpdateTaskDevice).where(UpdateTaskDevice.task_id == task_id).order_by(UpdateTaskDevice.id.asc())
            )
        )

    def to_read(self, session: Session, task: UpdateTask) -> UpdateTaskRead:
        rows = self.device_rows(session, task.id)
        return UpdateTaskRead.model_validate(task).model_copy(update={"device_count": len(rows), "devices": rows})

    def _target_devices(self, session: Session, target_filter: dict[str, Any] | None) -> list[Device]:
        target_filter = target_filter or {}
        statement = select(Device)
        if project_id := target_filter.get("project_id"):
            statement = statement.where(Device.project_id == str(project_id))
        if group_id := target_filter.get("group_id"):
            statement = statement.where(Device.group_id == int(group_id))
        if status := target_filter.get("status"):
            statement = statement.where(Device.status == str(status))
        if device_ids := target_filter.get("device_ids"):
            statement = statement.where(Device.id.in_([int(device_id) for device_id in device_ids]))

        devices = list(session.scalars(statement.order_by(Device.id.asc())))
        tags = target_filter.get("tags")
        if isinstance(tags, str):
            tags = [tags]
        if tags:
            required_tags = {str(tag) for tag in tags}
            devices = [device for device in devices if required_tags.issubset(set(device.tags or []))]
        return devices
