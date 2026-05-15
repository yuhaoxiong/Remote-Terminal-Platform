from pydantic import BaseModel


class DiagnosticsSecuritySummary(BaseModel):
    credential_encryption_configured: bool
    jwt_secret_configured: bool
    default_admin_password_in_use: bool
    default_device_ssh_password_in_use: bool
    warnings: list[str] = []


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
    security: DiagnosticsSecuritySummary
