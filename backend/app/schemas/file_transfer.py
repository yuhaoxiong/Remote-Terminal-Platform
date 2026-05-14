from datetime import datetime

from pydantic import BaseModel, Field


class FileItem(BaseModel):
    name: str
    path: str
    type: str
    size: int
    modified_at: datetime | None = None


class FileListResponse(BaseModel):
    device_id: int
    path: str
    items: list[FileItem]


class FileUploadRequest(BaseModel):
    remote_path: str = Field(min_length=1)
    content: str = ""


class FileDeleteRequest(BaseModel):
    remote_path: str = Field(min_length=1)


class FileOperationResponse(BaseModel):
    device_id: int
    remote_path: str
    status: str
    size: int | None = None
