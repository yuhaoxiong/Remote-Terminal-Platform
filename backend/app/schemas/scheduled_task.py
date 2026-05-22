from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import ExecutionMode, FailureStrategy, ScheduledTaskRunStatus, ScheduledTaskRunTriggerType, ScheduledTaskType
from app.services.schedule_parser import ScheduleExpressionError, parse_schedule_trigger


def _validate_schedule(value: str) -> str:
    try:
        parse_schedule_trigger(value)
    except ScheduleExpressionError as exc:
        raise ValueError(str(exc)) from exc
    return value


class ScheduledTaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    task_type: ScheduledTaskType
    schedule: str = Field(min_length=1, max_length=120)
    command: str | None = None
    target_filter: dict[str, Any] | None = None
    enabled: bool = True
    execution_mode: ExecutionMode = ExecutionMode.dry_run
    failure_strategy: FailureStrategy = FailureStrategy.continue_
    concurrency_limit: int = Field(default=5, ge=1, le=50)

    @field_validator("schedule")
    @classmethod
    def schedule_prefix(cls, value: str) -> str:
        return _validate_schedule(value)


class ScheduledTaskUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    task_type: ScheduledTaskType | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    command: str | None = None
    target_filter: dict[str, Any] | None = None
    enabled: bool | None = None
    execution_mode: ExecutionMode | None = None
    failure_strategy: FailureStrategy | None = None
    concurrency_limit: int | None = Field(default=None, ge=1, le=50)

    @field_validator("schedule")
    @classmethod
    def schedule_prefix(cls, value: str | None) -> str | None:
        return _validate_schedule(value) if value is not None else value


class ScheduledTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    task_type: str
    schedule: str
    command: str | None
    target_filter: dict[str, Any] | None
    enabled: bool
    execution_mode: str
    failure_strategy: str
    concurrency_limit: int
    last_run_at: datetime | None
    last_status: str | None
    last_error: str | None
    next_run_at: datetime | None
    running: bool
    created_at: datetime
    updated_at: datetime


class ScheduledTaskListResponse(BaseModel):
    total: int
    items: list[ScheduledTaskRead]


class ScheduledTaskExecuteResponse(BaseModel):
    task_id: int
    status: str
    output_summary: str
    run_id: int | None = None


class ScheduledTaskRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scheduled_task_id: int
    trigger_type: ScheduledTaskRunTriggerType | str
    status: ScheduledTaskRunStatus | str
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    output_summary: str | None
    error_message: str | None
    created_update_task_id: int | None
    created_at: datetime


class ScheduledTaskRunListResponse(BaseModel):
    total: int
    items: list[ScheduledTaskRunRead]


class SchedulerStatusResponse(BaseModel):
    enabled: bool
    running: bool
    poll_interval_seconds: int
    last_scan_at: datetime | None
    last_error: str | None
    job_count: int
