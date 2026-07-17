from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeploymentPlanCreate(BaseModel):
    device_ids: list[int] = Field(min_length=1, max_length=5)


class DeviceReleaseOverrideSet(BaseModel):
    release_id: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)
    expires_at: datetime


class DeviceReleaseOverrideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    function_id: int
    release_id: int
    reason: str
    expires_at: datetime
    active: bool
    created_by: int
    created_at: datetime
    updated_at: datetime


class DeploymentPlanItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    device_id: int
    function_id: int
    release_id: int
    variant_id: int
    config_snapshot: dict | None
    config_hash: str
    artifact_sha256: str
    preflight_json: dict | None
    status: str
    created_at: datetime


class DeploymentPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    status: str
    snapshot_hash: str
    expires_at: datetime
    stale_reason: str | None
    created_by: int
    confirmed_by: int | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[DeploymentPlanItemRead] = Field(default_factory=list)


class DeploymentExecutionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    deployment_execution_id: int
    plan_item_id: int
    status: str
    attempt_count: int
    result_json: dict | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DeploymentExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    execution_id: str
    plan_id: int
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    created_by: int
    created_at: datetime
    updated_at: datetime
    items: list[DeploymentExecutionItemRead] = Field(default_factory=list)
