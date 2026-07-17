from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import ExecutionMode, FailureStrategy, ScheduledTaskType


class UpdateTaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    task_type: ScheduledTaskType
    command: str = Field(min_length=1)
    rollback_command: str | None = None
    target_filter: dict[str, Any] | None = None
    execution_mode: ExecutionMode = ExecutionMode.dry_run
    failure_strategy: FailureStrategy = FailureStrategy.continue_
    concurrency_limit: int = Field(default=5, ge=1, le=50)

    @model_validator(mode="after")
    def require_rollback_command(self) -> "UpdateTaskCreate":
        if self.failure_strategy == FailureStrategy.rollback and not self.rollback_command:
            raise ValueError("rollback_command is required when failure_strategy is rollback")
        return self


class UpdateTaskDeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    device_id: int
    status: str
    output_summary: str | None
    exit_code: int | None
    stdout_summary: str | None
    stderr_summary: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None


class UpdateTaskTargetPreviewRequest(BaseModel):
    target_filter: dict[str, Any] | None = None
    execution_mode: ExecutionMode = ExecutionMode.dry_run


class UpdateTaskTargetDeviceRead(BaseModel):
    id: int
    name: str
    device_sn: str
    project_id: int | None
    group_id: int | None
    status: str
    ssh_port: int | None
    ssh_credential_configured: bool
    tags: list[str] | None = None
    location: str | None = None


class UpdateTaskTargetPreviewResponse(BaseModel):
    total: int
    items: list[UpdateTaskTargetDeviceRead]
    warnings: list[str] = []


class UpdateTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    task_type: str
    command: str
    rollback_command: str | None
    target_filter: dict[str, Any] | None
    execution_mode: str
    failure_strategy: str
    concurrency_limit: int
    status: str
    created_at: datetime
    updated_at: datetime
    device_count: int = 0
    devices: list[UpdateTaskDeviceRead] = []


class UpdateTaskListResponse(BaseModel):
    total: int
    items: list[UpdateTaskRead]


class UpdateTaskTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    command: str = Field(min_length=1, max_length=4000)
    task_type: ScheduledTaskType = ScheduledTaskType.command
    default_execution_mode: ExecutionMode = ExecutionMode.dry_run


class UpdateTaskTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    command: str | None = Field(default=None, min_length=1, max_length=4000)
    task_type: ScheduledTaskType | None = None
    default_execution_mode: ExecutionMode | None = None


class UpdateTaskTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    command: str
    task_type: str
    default_execution_mode: str
    created_at: datetime
    updated_at: datetime


class UpdateTaskTemplateListResponse(BaseModel):
    total: int
    items: list[UpdateTaskTemplateRead]
