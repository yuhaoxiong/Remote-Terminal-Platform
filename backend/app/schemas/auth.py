from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
