from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import ScheduledTaskType


def _validate_schedule(value: str) -> str:
    if not (value.startswith("cron:") or value.startswith("interval:")):
        raise ValueError("schedule must start with cron: or interval:")
    return value


class ScheduledTaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    task_type: ScheduledTaskType
    schedule: str = Field(min_length=1, max_length=120)
    command: str | None = None
    target_filter: dict[str, Any] | None = None
    enabled: bool = True

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
    created_at: datetime
    updated_at: datetime


class ScheduledTaskListResponse(BaseModel):
    total: int
    items: list[ScheduledTaskRead]


class ScheduledTaskExecuteResponse(BaseModel):
    task_id: int
    status: str
    output_summary: str
