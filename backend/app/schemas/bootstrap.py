from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeviceBootstrapPackageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    generation: int
    status: str
    validation_errors: list[str] | None
    config_hash: str | None
    ca_sha256: str | None
    downloaded_at: datetime | None
    invalidated_at: datetime | None
    claimed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DeviceHardwareReport(BaseModel):
    soc: str = Field(min_length=1, max_length=64)
    memory_mb: int = Field(gt=0)
    os_version: str = Field(min_length=1, max_length=120)


class DeviceRegistrationClaim(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    device_uuid: str = Field(min_length=36, max_length=36)
    device_sn: str = Field(min_length=1, max_length=120)
    machine_id: str | None = Field(default=None, max_length=255)
    mac_addresses: list[str] = Field(default_factory=list, max_length=32)
    hardware: DeviceHardwareReport
    ssh_ready: bool
    vnc_ready: bool = False
    bootstrap_status: Literal["ready", "reboot_required", "failed"]
    error_message: str | None = Field(default=None, max_length=1000)

    @field_validator("mac_addresses")
    @classmethod
    def normalize_macs(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().lower() for item in value if item.strip()})


class DeviceRegistrationResponse(BaseModel):
    device_id: int
    accepted: bool
    status: str
    vnc_status: str
    hardware_profile_id: int | None
    hardware_matches_expected: bool | None
