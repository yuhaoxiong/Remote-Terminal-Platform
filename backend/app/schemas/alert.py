from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import AlertRuleType, AlertSeverity, AlertSourceType, AlertStatus


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dedupe_key: str
    alert_type: str
    severity: AlertSeverity | str
    status: AlertStatus | str
    source_type: AlertSourceType | str
    source_id: int | None
    device_id: int | None
    title: str
    summary: str
    detail: str | None
    first_triggered_at: datetime
    last_triggered_at: datetime
    trigger_count: int
    acknowledged_at: datetime | None
    acknowledged_note: str | None
    resolved_at: datetime | None
    resolved_by: str | None
    created_at: datetime
    updated_at: datetime


class AlertListResponse(BaseModel):
    total: int
    items: list[AlertRead]


class AlertSummaryResponse(BaseModel):
    active_count: int
    critical_count: int
    unacknowledged_count: int
    latest_alert_at: datetime | None
    by_source: dict[str, int] = {}
    by_severity: dict[str, int] = {}


class AlertAcknowledgeRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class AlertResolveRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class AlertRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_type: AlertRuleType | str
    enabled: bool
    severity: AlertSeverity | str
    threshold_value: float | None
    window_minutes: int | None
    created_at: datetime
    updated_at: datetime


class AlertRuleUpdate(BaseModel):
    enabled: bool | None = None
    severity: AlertSeverity | None = None
    threshold_value: float | None = Field(default=None, ge=0, le=100)
    window_minutes: int | None = Field(default=None, ge=1, le=1440)

    @model_validator(mode="after")
    def validate_payload(self) -> "AlertRuleUpdate":
        if not self.model_fields_set:
            raise ValueError("至少需要更新一个字段")
        return self


class AlertRuleListResponse(BaseModel):
    total: int
    items: list[AlertRuleRead]
