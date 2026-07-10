from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums import DeviceStatus, SshAuthType


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    device_sn: str = Field(min_length=1, max_length=120)
    project_id: str = Field(min_length=1, max_length=120)
    location: str | None = Field(default=None, max_length=255)
    hardware_model: str | None = Field(default=None, max_length=120)
    ssh_user: str = Field(default="ztl", min_length=1, max_length=64)
    ssh_auth_type: SshAuthType = SshAuthType.password
    ssh_password: str | None = Field(default="123456", max_length=255)
    local_ip: str | None = Field(default=None, max_length=64)
    os_version: str | None = Field(default=None, max_length=120)
    description: str | None = None
    tags: list[str] | None = None
    group_id: int | None = None
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    vnc_port: int | None = Field(default=None, ge=1, le=65535)


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    project_id: str | None = Field(default=None, min_length=1, max_length=120)
    location: str | None = Field(default=None, max_length=255)
    hardware_model: str | None = Field(default=None, max_length=120)
    ssh_user: str | None = Field(default=None, min_length=1, max_length=64)
    ssh_auth_type: SshAuthType | None = None
    ssh_password: str | None = Field(default=None, max_length=255)
    local_ip: str | None = Field(default=None, max_length=64)
    os_version: str | None = Field(default=None, max_length=120)
    description: str | None = None
    tags: list[str] | None = None
    group_id: int | None = None
    status: DeviceStatus | None = None
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    vnc_port: int | None = Field(default=None, ge=1, le=65535)


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    device_sn: str
    project_id: str
    location: str | None
    hardware_model: str | None
    ssh_port: int | None
    vnc_port: int | None
    ssh_user: str
    ssh_auth_type: str
    ssh_credential_configured: bool
    local_ip: str | None
    os_version: str | None
    description: str | None
    tags: list[str] | None
    group_id: int | None
    status: str
    last_seen: datetime | None
    created_at: datetime
    updated_at: datetime


class DeviceListResponse(BaseModel):
    total: int
    items: list[DeviceRead]


class DeviceStatusResponse(BaseModel):
    id: int
    status: str
    last_seen: datetime | None


class SyncConfigResponse(BaseModel):
    device_id: int
    status: str
    config: str


class DeviceMetricCreate(BaseModel):
    status: DeviceStatus = DeviceStatus.online
    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    memory_percent: float | None = Field(default=None, ge=0, le=100)
    disk_percent: float | None = Field(default=None, ge=0, le=100)
    temperature_celsius: float | None = None
    load_average: float | None = Field(default=None, ge=0)


class DeviceMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    status: str = "unknown"
    cpu_percent: float | None
    memory_percent: float | None
    disk_percent: float | None
    temperature_celsius: float | None
    load_average: float | None
    recorded_at: datetime


class DeviceMetricListResponse(BaseModel):
    total: int
    items: list[DeviceMetricRead]


class RemoteSessionResponse(BaseModel):
    device_id: int
    session_type: str
    status: str
    remote_port: int
    websocket_url: str | None = None
    proxy_url: str | None = None
    vnc_password: str | None = None
