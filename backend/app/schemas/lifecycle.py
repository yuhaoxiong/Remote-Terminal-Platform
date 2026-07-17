from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CODE_PATTERN = r"^[a-z0-9][a-z0-9-]{1,63}$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class ProjectCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=CODE_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    status: Literal["active", "archived"] | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ProjectUpdate":
        if not self.model_fields_set:
            raise ValueError("至少需要更新一个字段")
        return self


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    total: int
    items: list[ProjectRead]


class HardwareProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    soc: str
    memory_mb: int
    os_version: str
    rknn_version: str | None
    active: bool


class HardwareProfileListResponse(BaseModel):
    total: int
    items: list[HardwareProfileRead]


class FunctionCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=CODE_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class FunctionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    status: Literal["active", "archived"] | None = None

    @model_validator(mode="after")
    def require_change(self) -> "FunctionUpdate":
        if not self.model_fields_set:
            raise ValueError("至少需要更新一个字段")
        return self


class FunctionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class FunctionListResponse(BaseModel):
    total: int
    items: list[FunctionRead]


class FunctionReleaseCreate(BaseModel):
    version: str = Field(min_length=1, max_length=64)
    manifest_json: dict[str, Any] | None = None
    release_notes: str | None = None


class FunctionReleaseUpdate(BaseModel):
    manifest_json: dict[str, Any] | None = None
    release_notes: str | None = None

    @model_validator(mode="after")
    def require_change(self) -> "FunctionReleaseUpdate":
        if not self.model_fields_set:
            raise ValueError("至少需要更新一个字段")
        return self


class FunctionReleaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    function_id: int
    version: str
    status: str
    manifest_json: dict[str, Any] | None
    release_notes: str | None
    published_at: datetime | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class FunctionReleaseListResponse(BaseModel):
    total: int
    items: list[FunctionReleaseRead]


class FunctionVariantCreate(BaseModel):
    hardware_profile_id: int = Field(ge=1)
    artifact_uri: str = Field(min_length=1, max_length=500)
    artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    artifact_size: int = Field(gt=0)
    signature: str | None = None
    key_id: str | None = Field(default=None, max_length=120)


class FunctionVariantUpdate(BaseModel):
    artifact_uri: str | None = Field(default=None, min_length=1, max_length=500)
    artifact_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    artifact_size: int | None = Field(default=None, gt=0)
    signature: str | None = None
    key_id: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def require_change(self) -> "FunctionVariantUpdate":
        if not self.model_fields_set:
            raise ValueError("至少需要更新一个字段")
        return self


class FunctionVariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    release_id: int
    hardware_profile_id: int
    artifact_uri: str
    artifact_sha256: str
    artifact_size: int
    signature: str | None
    key_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class FunctionVariantListResponse(BaseModel):
    total: int
    items: list[FunctionVariantRead]


class ProjectFunctionSet(BaseModel):
    desired_release_id: int = Field(ge=1)
    config_json: dict[str, Any] | None = None


class ProjectFunctionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    function_id: int
    desired_release_id: int
    config_json: dict[str, Any] | None
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectFunctionListResponse(BaseModel):
    total: int
    items: list[ProjectFunctionRead]
