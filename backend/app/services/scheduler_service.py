from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import Settings
from app.database import session_scope
from app.enums import ScheduledTaskRunTriggerType
from app.services.scheduled_task_service import ScheduledTaskService
from app.services.ssh_service import SshService


@dataclass(frozen=True)
class SchedulerStatus:
    enabled: bool
    running: bool
    poll_interval_seconds: int
    last_scan_at: datetime | None
    last_error: str | None
    job_count: int


class SchedulerService:
    scan_job_id = "scheduled-task-scan"

    def __init__(self, settings: Settings, ssh_service: SshService | None = None) -> None:
        self.settings = settings
        self.ssh_service = ssh_service
        self.last_scan_at: datetime | None = None
        self.last_error: str | None = None
        self.scheduler: BackgroundScheduler | None = None

    def start(self) -> None:
        if not self.settings.scheduler_enabled or self.scheduler is not None:
            return
        self.scheduler = BackgroundScheduler(timezone=timezone.utc)
        self.scheduler.add_job(
            self.scan_due_tasks,
            "interval",
            seconds=self.settings.scheduler_poll_interval_seconds,
            id=self.scan_job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler is None:
            return
        self.scheduler.shutdown(wait=False)
        self.scheduler = None

    def status(self) -> SchedulerStatus:
        return SchedulerStatus(
            enabled=self.settings.scheduler_enabled,
            running=bool(self.scheduler and self.scheduler.running),
            poll_interval_seconds=self.settings.scheduler_poll_interval_seconds,
            last_scan_at=self.last_scan_at,
            last_error=self.last_error,
            job_count=len(self.scheduler.get_jobs()) if self.scheduler is not None else 0,
        )

    def scan_due_tasks(self) -> int:
        if not self.settings.scheduler_enabled:
            return 0
        self.last_scan_at = datetime.now(timezone.utc)
        try:
            with session_scope(self.settings) as session:
                service = ScheduledTaskService(self.settings, ssh_service=self.ssh_service)
                due_tasks = service.due_tasks(session, self.last_scan_at)
                for task in due_tasks:
                    service.run_now(
                        session,
                        task.id,
                        user_id=None,
                        trigger_type=ScheduledTaskRunTriggerType.scheduled,
                    )
                self.last_error = None
                return len(due_tasks)
        except Exception as exc:
            self.last_error = str(exc)
            return 0
