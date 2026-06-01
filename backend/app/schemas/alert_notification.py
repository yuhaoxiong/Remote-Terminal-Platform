from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums import (
    AlertNotificationChannelType,
    AlertNotificationDeliveryStatus,
    AlertNotificationEventType,
    AlertSeverity,
    AlertSourceType,
)


class AlertNotificationChannelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    channel_type: AlertNotificationChannelType | str
    enabled: bool
    webhook_url_preview: str | None = None
    timeout_seconds: int
    header_keys: list[str] = Field(default_factory=list)
    secret_configured: bool
    last_test_status: str | None
    last_test_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class AlertNotificationChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    channel_type: AlertNotificationChannelType = AlertNotificationChannelType.webhook
    enabled: bool = True
    webhook_url: str = Field(min_length=1, max_length=1000)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=5, ge=1, le=30)

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("Webhook URL 必须以 http:// 或 https:// 开头")
        return value


class AlertNotificationChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    webhook_url: str | None = Field(default=None, min_length=1, max_length=1000)
    headers: dict[str, str] | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=30)

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            raise ValueError("Webhook URL 必须以 http:// 或 https:// 开头")
        return value

    @model_validator(mode="after")
    def validate_payload(self) -> "AlertNotificationChannelUpdate":
        if not self.model_fields_set:
            raise ValueError("至少需要更新一个字段")
        return self


class AlertNotificationChannelListResponse(BaseModel):
    total: int
    items: list[AlertNotificationChannelRead]


class AlertNotificationPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    enabled: bool
    channel_id: int
    min_severity: AlertSeverity | str
    source_types: list[str] = Field(default_factory=list)
    alert_statuses: list[str] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AlertNotificationPolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    channel_id: int = Field(ge=1)
    min_severity: AlertSeverity = AlertSeverity.critical
    source_types: list[AlertSourceType] = Field(default_factory=list)
    alert_statuses: list[str] = Field(default_factory=list)
    event_types: list[AlertNotificationEventType] = Field(
        default_factory=lambda: [AlertNotificationEventType.triggered]
    )


class AlertNotificationPolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    channel_id: int | None = Field(default=None, ge=1)
    min_severity: AlertSeverity | None = None
    source_types: list[AlertSourceType] | None = None
    alert_statuses: list[str] | None = None
    event_types: list[AlertNotificationEventType] | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "AlertNotificationPolicyUpdate":
        if not self.model_fields_set:
            raise ValueError("至少需要更新一个字段")
        return self


class AlertNotificationPolicyListResponse(BaseModel):
    total: int
    items: list[AlertNotificationPolicyRead]


class AlertNotificationDeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: int
    channel_id: int
    policy_id: int
    event_type: AlertNotificationEventType | str
    status: AlertNotificationDeliveryStatus | str
    attempt_count: int
    last_attempt_at: datetime | None
    next_retry_at: datetime | None
    response_status_code: int | None
    response_summary: str | None
    error_message: str | None
    alert_title: str | None = None
    channel_name: str | None = None
    policy_name: str | None = None
    created_at: datetime
    updated_at: datetime


class AlertNotificationDeliveryListResponse(BaseModel):
    total: int
    items: list[AlertNotificationDeliveryRead]


class AlertNotificationSummaryResponse(BaseModel):
    enabled_channel_count: int
    enabled_policy_count: int
    failed_delivery_count: int
    retrying_delivery_count: int
    last_delivery_at: datetime | None
    warnings: list[str] = Field(default_factory=list)
