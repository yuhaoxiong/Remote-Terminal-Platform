from pydantic import BaseModel


class DiagnosticsConfigResponse(BaseModel):
    service_name: str
    version: str
    api_prefix: str
    database: str
    file_backend: str
    remote_gateway_host: str
    vnc_gateway_host: str
    ssh_timeout_seconds: int
    vnc_timeout_seconds: int
    default_device_ssh_user: str
