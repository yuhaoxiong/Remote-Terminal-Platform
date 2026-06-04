from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole | str
    is_active: bool
    last_login_at: datetime | None
    last_login_ip: str | None
    password_changed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    total: int
    items: list[UserRead]


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8)
    role: UserRole = UserRole.operator
    is_active: bool = True


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "UserUpdate":
        if not self.model_fields_set:
            raise ValueError("至少需要更新一个字段")
        return self


class UserResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class UserToggleRequest(BaseModel):
    is_active: bool
