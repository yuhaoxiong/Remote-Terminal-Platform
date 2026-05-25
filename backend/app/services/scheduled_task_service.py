from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.enums import ScheduledTaskRunStatus, ScheduledTaskRunTriggerType
from app.models.log import OperationLog
from app.models.scheduled_task import ScheduledTask, ScheduledTaskRun
from app.schemas.scheduled_task import ScheduledTaskCreate, ScheduledTaskUpdate
from app.schemas.update_task import UpdateTaskCreate
from app.services.alert_service import AlertService
from app.services.operation_log import OperationLogService
from app.services.schedule_parser import next_run_time
from app.services.ssh_service import SshService
from app.services.update_task_service import UpdateTaskService


class ScheduledTaskNotFoundError(RuntimeError):
    pass


class ScheduledTaskService:
    def __init__(self, settings: Settings, ssh_service: SshService | None = None) -> None:
        self.settings = settings
        self.ssh_service = ssh_service

    def create(self, session: Session, payload: ScheduledTaskCreate) -> ScheduledTask:
        task = ScheduledTask(**payload.model_dump())
        task.next_run_at = self.calculate_next_run_at(task) if task.enabled else None
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
        task.next_run_at = self.calculate_next_run_at(task) if task.enabled else None
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
        task.next_run_at = self.calculate_next_run_at(task) if task.enabled else None
        session.flush()
        session.refresh(task)
        return task

    def execute(self, session: Session, task_id: int, *, user_id: int | None) -> str:
        run = self.run_now(session, task_id, user_id=user_id, trigger_type=ScheduledTaskRunTriggerType.manual)
        return run.output_summary or run.error_message or run.status

    def run_now(
        self,
        session: Session,
        task_id: int,
        *,
        user_id: int | None,
        trigger_type: ScheduledTaskRunTriggerType | str,
    ) -> ScheduledTaskRun:
        task = self.get(session, task_id)
        trigger_value = str(trigger_type.value if isinstance(trigger_type, ScheduledTaskRunTriggerType) else trigger_type)
        if task.running:
            return self._create_skipped_run(session, task, trigger_value, user_id, "任务仍在运行，跳过本次触发")

        run = ScheduledTaskRun(
            scheduled_task_id=task.id,
            trigger_type=trigger_value,
            status=ScheduledTaskRunStatus.running.value,
            started_at=datetime.now(timezone.utc),
        )
        task.running = True
        session.add(run)
        session.flush()
        try:
            if task.task_type != "command":
                summary = f"simulated scheduled task execution: {task.command or task.task_type}"
                status = (
                    ScheduledTaskRunStatus.success.value
                    if trigger_value == ScheduledTaskRunTriggerType.manual.value
                    else ScheduledTaskRunStatus.skipped.value
                )
                self._finish_run(session, task, run, status, summary, None)
                self._record_run_log(session, task, run, user_id)
                return run
            if not task.command:
                self._finish_run(session, task, run, ScheduledTaskRunStatus.failed.value, None, "命令不能为空")
                self._record_run_log(session, task, run, user_id)
                return run

            update_service = UpdateTaskService(self.settings, ssh_service=self.ssh_service)
            target_devices = update_service.target_devices(session, task.target_filter)
            if not target_devices:
                self._finish_run(session, task, run, ScheduledTaskRunStatus.skipped.value, "未匹配到目标设备", None)
                self._record_run_log(session, task, run, user_id)
                return run

            update_task = update_service.create(
                session,
                UpdateTaskCreate(
                    name=f"{task.name} - 定时触发",
                    task_type="command",
                    command=task.command,
                    target_filter=task.target_filter,
                    execution_mode=task.execution_mode,
                    failure_strategy=task.failure_strategy,
                    concurrency_limit=task.concurrency_limit,
                ),
            )
            update_task = update_service.execute(session, update_task.id)
            stats = update_service.execution_stats(session, update_task)
            summary = (
                f"已触发批量任务 #{update_task.id}，模式 {stats['execution_mode']}，"
                f"总数 {stats['total']}，成功 {stats['success']}，失败 {stats['failed']}，跳过 {stats['skipped']}"
            )
            run.created_update_task_id = update_task.id
            status = ScheduledTaskRunStatus.success.value if update_task.status == "completed" else ScheduledTaskRunStatus.failed.value
            error = None if status == ScheduledTaskRunStatus.success.value else f"批量任务状态：{update_task.status}"
            self._finish_run(session, task, run, status, summary, error)
            self._record_run_log(session, task, run, user_id)
            return run
        except Exception as exc:
            self._finish_run(session, task, run, ScheduledTaskRunStatus.failed.value, None, str(exc))
            self._record_run_log(session, task, run, user_id)
            return run

    def list_runs(
        self,
        session: Session,
        task_id: int,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[int, list[ScheduledTaskRun]]:
        self.get(session, task_id)
        count_statement = select(func.count(ScheduledTaskRun.id)).where(ScheduledTaskRun.scheduled_task_id == task_id)
        statement = (
            select(ScheduledTaskRun)
            .where(ScheduledTaskRun.scheduled_task_id == task_id)
            .order_by(ScheduledTaskRun.created_at.desc(), ScheduledTaskRun.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return session.scalar(count_statement) or 0, list(session.scalars(statement))

    def due_tasks(self, session: Session, now: datetime | None = None) -> list[ScheduledTask]:
        now = now or datetime.now(timezone.utc)
        return list(
            session.scalars(
                select(ScheduledTask)
                .where(
                    ScheduledTask.enabled.is_(True),
                    ScheduledTask.running.is_(False),
                    ScheduledTask.next_run_at.is_not(None),
                    ScheduledTask.next_run_at <= now,
                )
                .order_by(ScheduledTask.next_run_at.asc(), ScheduledTask.id.asc())
            )
        )

    def calculate_next_run_at(self, task: ScheduledTask) -> datetime:
        return next_run_time(task.schedule)

    def _create_skipped_run(
        self,
        session: Session,
        task: ScheduledTask,
        trigger_type: str,
        user_id: int | None,
        message: str,
    ) -> ScheduledTaskRun:
        now = datetime.now(timezone.utc)
        run = ScheduledTaskRun(
            scheduled_task_id=task.id,
            trigger_type=trigger_type,
            status=ScheduledTaskRunStatus.skipped.value,
            started_at=now,
            finished_at=now,
            duration_ms=0,
            output_summary=message,
        )
        task.last_run_at = now
        task.last_status = run.status
        task.last_error = None
        task.next_run_at = self.calculate_next_run_at(task) if task.enabled else None
        session.add(run)
        session.flush()
        self._record_run_log(session, task, run, user_id)
        return run

    def _finish_run(
        self,
        session: Session,
        task: ScheduledTask,
        run: ScheduledTaskRun,
        status: str,
        output_summary: str | None,
        error_message: str | None,
    ) -> None:
        finished_at = datetime.now(timezone.utc)
        started_at = run.started_at or finished_at
        run.status = status
        run.finished_at = finished_at
        run.duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
        run.output_summary = output_summary
        run.error_message = error_message
        task.running = False
        task.last_run_at = finished_at
        task.last_status = status
        task.last_error = error_message
        task.next_run_at = self.calculate_next_run_at(task) if task.enabled else None
        session.flush()
        AlertService(self.settings).handle_scheduled_task_run(session, task, run)

    def _record_run_log(
        self,
        session: Session,
        task: ScheduledTask,
        run: ScheduledTaskRun,
        user_id: int | None,
    ) -> None:
        action = f"scheduled_task.run.{run.trigger_type}"
        if run.status == ScheduledTaskRunStatus.failed.value:
            action = "scheduled_task.run.failed"
        detail = run.output_summary or run.error_message or run.status
        OperationLogService(self.settings).record(
            session,
            user_id=user_id,
            action=action,
            target_type="scheduled_task",
            target_id=task.id,
            status=run.status,
            detail=detail,
        )

    def logs(self, session: Session, task_id: int) -> tuple[int, list[OperationLog]]:
        self.get(session, task_id)
        statement = (
            select(OperationLog)
            .where(OperationLog.target_type == "scheduled_task", OperationLog.target_id == task_id)
            .order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
        )
        logs = list(session.scalars(statement))
        return len(logs), logs
