from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import false, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.device import Device
from app.models.update_task import UpdateTask, UpdateTaskDevice, UpdateTaskTemplate
from app.schemas.update_task import (
    UpdateTaskCreate,
    UpdateTaskRead,
    UpdateTaskTargetDeviceRead,
    UpdateTaskTargetPreviewResponse,
    UpdateTaskTemplateCreate,
    UpdateTaskTemplateUpdate,
)
from app.services.alert_service import AlertService
from app.services.ssh_service import RemoteAuthenticationError, RemoteConnectionError, SshService


class UpdateTaskNotFoundError(RuntimeError):
    pass


class UpdateTaskInvalidStateError(RuntimeError):
    pass


class UpdateTaskTemplateNotFoundError(RuntimeError):
    pass


class UpdateTaskService:
    output_limit = 4000

    def __init__(self, settings: Settings, ssh_service: SshService | None = None) -> None:
        self.settings = settings
        self.ssh_service = ssh_service or SshService(settings)

    def create(self, session: Session, payload: UpdateTaskCreate) -> UpdateTask:
        task = UpdateTask(**payload.model_dump())
        session.add(task)
        session.flush()
        for device in self.target_devices(session, payload.target_filter):
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
        rows = self.device_rows(session, task.id)
        if task.execution_mode == "ssh_command":
            self._execute_ssh_command(session, task, rows)
        else:
            self._execute_dry_run(task, rows)
        task.status = self._final_task_status(rows, dry_run=task.execution_mode != "ssh_command")
        session.flush()
        AlertService(self.settings).handle_update_task_completed(session, task)
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

    def execution_stats(self, session: Session, task: UpdateTask) -> dict[str, int | str]:
        rows = self.device_rows(session, task.id)
        return {
            "execution_mode": task.execution_mode,
            "total": len(rows),
            "success": sum(1 for row in rows if row.status == "success"),
            "failed": sum(1 for row in rows if row.status == "failed"),
            "skipped": sum(1 for row in rows if row.status == "skipped"),
        }

    def target_devices(self, session: Session, target_filter: dict[str, Any] | None) -> list[Device]:
        target_filter = target_filter or {}
        statement = select(Device)
        if project_id := target_filter.get("project_id"):
            statement = statement.where(
                Device.project_id == project_id
                if isinstance(project_id, int) and not isinstance(project_id, bool)
                else false()
            )
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

    def preview_targets(
        self,
        session: Session,
        target_filter: dict[str, Any] | None,
        *,
        execution_mode: str = "dry_run",
    ) -> UpdateTaskTargetPreviewResponse:
        devices = self.target_devices(session, target_filter)
        items = [
            UpdateTaskTargetDeviceRead(
                id=device.id,
                name=device.name,
                device_sn=device.device_sn,
                project_id=device.project_id,
                group_id=device.group_id,
                status=device.status,
                ssh_port=device.ssh_port,
                ssh_credential_configured=device.ssh_credential_configured,
                tags=device.tags,
                location=device.location,
            )
            for device in devices
        ]
        warnings: list[str] = []
        if not devices:
            warnings.append("未匹配到目标设备")
        if execution_mode == "ssh_command":
            missing_port = sum(1 for device in devices if device.ssh_port is None)
            missing_credential = sum(1 for device in devices if not device.ssh_credential_configured)
            if missing_port:
                warnings.append(f"{missing_port} 台设备缺少 SSH 端口，将无法执行真实 SSH 命令")
            if missing_credential:
                warnings.append(f"{missing_credential} 台设备缺少 SSH 凭据，将无法执行真实 SSH 命令")
        return UpdateTaskTargetPreviewResponse(total=len(items), items=items, warnings=warnings)

    def list_templates(self, session: Session) -> tuple[int, list[UpdateTaskTemplate]]:
        statement = select(UpdateTaskTemplate).order_by(UpdateTaskTemplate.id.asc())
        total = session.scalar(select(func.count(UpdateTaskTemplate.id))) or 0
        return total, list(session.scalars(statement))

    def get_template(self, session: Session, template_id: int) -> UpdateTaskTemplate:
        template = session.get(UpdateTaskTemplate, template_id)
        if template is None:
            raise UpdateTaskTemplateNotFoundError(f"Update task template not found: {template_id}")
        return template

    def create_template(self, session: Session, payload: UpdateTaskTemplateCreate) -> UpdateTaskTemplate:
        template = UpdateTaskTemplate(**payload.model_dump())
        session.add(template)
        session.flush()
        session.refresh(template)
        return template

    def update_template(
        self,
        session: Session,
        template_id: int,
        payload: UpdateTaskTemplateUpdate,
    ) -> UpdateTaskTemplate:
        template = self.get_template(session, template_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(template, field, value)
        session.flush()
        session.refresh(template)
        return template

    def delete_template(self, session: Session, template_id: int) -> None:
        template = self.get_template(session, template_id)
        session.delete(template)
        session.flush()

    def _execute_dry_run(self, task: UpdateTask, rows: list[UpdateTaskDevice]) -> None:
        now = datetime.now(timezone.utc)
        for row in rows:
            if row.status != "pending":
                continue
            row.status = "skipped"
            row.started_at = now
            row.finished_at = datetime.now(timezone.utc)
            row.exit_code = None
            row.stdout_summary = None
            row.stderr_summary = None
            row.error_message = None
            row.output_summary = f"演练模式，未连接设备：{task.command}"

    def _execute_ssh_command(self, session: Session, task: UpdateTask, rows: list[UpdateTaskDevice]) -> None:
        stop_after_failure = False
        for row in rows:
            if row.status != "pending":
                continue
            if stop_after_failure:
                self._mark_skipped(row, "失败策略要求停止，跳过后续设备")
                continue
            device = session.get(Device, row.device_id)
            if device is None:
                self._mark_failed(row, "目标设备不存在")
            else:
                self._execute_device_command(row, device, task.command)
            if row.status == "failed" and task.failure_strategy in {"pause", "rollback"}:
                if task.failure_strategy == "rollback":
                    row.error_message = f"{row.error_message or '设备执行失败'}；回滚命令暂未自动执行"
                stop_after_failure = True

    def _execute_device_command(self, row: UpdateTaskDevice, device: Device, command: str) -> None:
        row.status = "running"
        row.started_at = datetime.now(timezone.utc)
        row.exit_code = None
        row.stdout_summary = None
        row.stderr_summary = None
        row.error_message = None
        try:
            exit_code, stdout_text, stderr_text = self.ssh_service.execute(device, command, self.settings.ssh_timeout_seconds)
        except RemoteAuthenticationError:
            self._mark_failed(row, "SSH 认证失败")
            return
        except RemoteConnectionError as exc:
            self._mark_failed(row, str(exc))
            return
        except Exception:
            self._mark_failed(row, "SSH 执行异常")
            return

        row.exit_code = exit_code
        row.stdout_summary = self._truncate(stdout_text)
        row.stderr_summary = self._truncate(stderr_text)
        row.finished_at = datetime.now(timezone.utc)
        if exit_code == 0:
            row.status = "success"
            row.output_summary = row.stdout_summary or "命令执行成功"
        else:
            row.status = "failed"
            row.error_message = f"命令退出码非 0：{exit_code}"
            row.output_summary = row.stderr_summary or row.error_message

    def _mark_failed(self, row: UpdateTaskDevice, message: str) -> None:
        row.status = "failed"
        row.started_at = row.started_at or datetime.now(timezone.utc)
        row.finished_at = datetime.now(timezone.utc)
        row.error_message = self._truncate(message)
        row.output_summary = row.error_message

    def _mark_skipped(self, row: UpdateTaskDevice, message: str) -> None:
        row.status = "skipped"
        row.started_at = row.started_at or datetime.now(timezone.utc)
        row.finished_at = datetime.now(timezone.utc)
        row.error_message = message
        row.output_summary = message

    def _truncate(self, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) <= self.output_limit:
            return value
        return value[: self.output_limit] + "...[已截断]"

    def _final_task_status(self, rows: list[UpdateTaskDevice], *, dry_run: bool) -> str:
        if not rows:
            return "completed"
        if dry_run:
            return "completed"
        return "completed" if all(row.status == "success" for row in rows) else "partial_failed"
