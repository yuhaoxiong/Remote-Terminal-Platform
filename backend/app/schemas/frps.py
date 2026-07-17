from pydantic import BaseModel, Field


class FrpsImportRequest(BaseModel):
    dashboard_url: str = Field(min_length=1)
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    ssh_port_start: int = 12001
    ssh_port_end: int = 17000
    vnc_port_start: int = 17001
    vnc_port_end: int = 22000
    project_id: int | None = Field(default=None, ge=1)
    location: str | None = "frps"
    overwrite_project_location: bool = False


class FrpsDiscoveredDevice(BaseModel):
    name: str
    device_sn: str
    project_id: int | None
    ssh_port: int
    vnc_port: int | None
    ssh_proxy_name: str
    vnc_proxy_name: str | None
    status: str
    import_status: str = "pending"
    detail: str | None = None
    existing_device_id: int | None = None


class FrpsImportResponse(BaseModel):
    total: int
    created: int
    skipped: int
    synced: int = 0
    conflicts: int = 0
    items: list[FrpsDiscoveredDevice]
