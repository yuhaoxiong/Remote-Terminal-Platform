from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.lifecycle import CODE_PATTERN


class ArtifactManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal[1]
    function_code: str = Field(pattern=CODE_PATTERN)
    version: str = Field(min_length=1, max_length=64)
    hardware_profile: str = Field(pattern=CODE_PATTERN)
    runtime: Literal["python-venv-systemd"]
    signature: str | None = None
    key_id: str | None = Field(default=None, max_length=120)
