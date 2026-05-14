from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UpdateTaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    task_type: str = Field(min_length=1, max_length=32)
    command: str = Field(min_length=1)
    rollback_command: str | None = None
    target_filter: dict[str, Any] | None = None
    failure_strategy: str = Field(default="continue", pattern="^(continue|pause|rollback)$")
    concurrency_limit: int = Field(default=5, ge=1, le=50)

    @model_validator(mode="after")
    def require_rollback_command(self) -> "UpdateTaskCreate":
        if self.failure_strategy == "rollback" and not self.rollback_command:
            raise ValueError("rollback_command is required when failure_strategy is rollback")
        return self


class UpdateTaskDeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    device_id: int
    status: str
    output_summary: str | None
    started_at: datetime | None
    finished_at: datetime | None


class UpdateTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    task_type: str
    command: str
    rollback_command: str | None
    target_filter: dict[str, Any] | None
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
