from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SystemSettingSchemaItem(BaseModel):
    key: str
    name: str
    description: str
    category: str
    value_type: str
    editable: bool
    secret: bool
    requires_restart: bool
    runtime_effective: bool
    options: list[str] | None = None
    min_value: int | None = None
    max_value: int | None = None


class SystemSettingSchemaResponse(BaseModel):
    groups: dict[str, str]
    items: list[SystemSettingSchemaItem]


class SystemSettingEffectiveItem(BaseModel):
    key: str
    name: str
    category: str
    value_type: str
    value: Any | None = None
    configured: bool = False
    source: str
    editable: bool
    secret: bool
    requires_restart: bool
    pending_restart: bool = False
    is_valid: bool = True
    invalid_reason: str | None = None
    updated_at: datetime | None = None


class SystemSettingEffectiveResponse(BaseModel):
    items: list[SystemSettingEffectiveItem]
    pending_restart_count: int
    database_override_count: int
    credential_encryption_configured: bool
    systemd_managed: bool


class SystemSettingGroupUpdate(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class SystemSettingGroupUpdateResponse(BaseModel):
    group: str
    updated_keys: list[str]
    requires_restart: bool
    pending_restart_count: int
    items: list[SystemSettingEffectiveItem]


class SystemSettingResetResponse(BaseModel):
    key: str
    source: str
    requires_restart: bool
    pending_restart_count: int


class SystemSettingChangeRead(BaseModel):
    id: int
    setting_key: str
    category: str
    action: str
    old_source: str | None
    new_source: str | None
    old_value_snapshot: str | None
    new_value_snapshot: str | None
    is_secret: bool
    requires_restart: bool
    pending_restart_after_change: bool
    actor_user_id: int | None
    actor_username: str | None
    client_ip: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SystemSettingChangeListResponse(BaseModel):
    total: int
    items: list[SystemSettingChangeRead]


class SystemSettingRestartRequest(BaseModel):
    confirm_text: str


class SystemSettingRestartResponse(BaseModel):
    status: str
    message: str
