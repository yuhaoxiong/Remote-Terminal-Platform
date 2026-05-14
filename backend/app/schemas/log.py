from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OperationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    action: str
    target_type: str | None
    target_id: int | None
    status: str
    detail: str | None
    created_at: datetime


class OperationLogListResponse(BaseModel):
    total: int
    items: list[OperationLogRead]
