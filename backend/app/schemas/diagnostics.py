from pydantic import BaseModel


class DiagnosticsSecuritySummary(BaseModel):
    credential_encryption_configured: bool
    jwt_secret_configured: bool
    default_admin_password_in_use: bool
    default_device_ssh_password_in_use: bool
    warnings: list[str] = []


class DiagnosticsMigrationSummary(BaseModel):
    current_revision: str | None
    head_revision: str | None
    has_pending_migrations: bool
    last_error: str | None = None


class DiagnosticsSshHostKeySummary(BaseModel):
    policy: str
    known_hosts_configured: bool
    warnings: list[str] = []


class DiagnosticsAuthLifetimeSummary(BaseModel):
    access_expire_minutes: int
    refresh_expire_minutes: int
    jwt_secret_configured: bool


class DiagnosticsDatabaseSummary(BaseModel):
    summary: str
    sqlite_backup_recommended: bool


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
    migration: DiagnosticsMigrationSummary
    ssh_host_key: DiagnosticsSshHostKeySummary
    auth_lifetime: DiagnosticsAuthLifetimeSummary
    database_status: DiagnosticsDatabaseSummary
