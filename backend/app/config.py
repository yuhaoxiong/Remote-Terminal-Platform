from functools import lru_cache
import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    service_name: str = "edge-platform"
    version: str = "0.1.0"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./data/platform.db"
    jwt_secret_key: str = Field(default="change-me-in-production", min_length=8)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24
    default_admin_username: str = "admin"
    default_admin_password: str = "admin"
    ssh_port_start: int = 10000
    ssh_port_end: int = 10499
    vnc_port_start: int = 10500
    vnc_port_end: int = 10999
    health_check_interval_seconds: int = 60
    ssh_timeout_seconds: int = 10
    vnc_timeout_seconds: int = 10
    file_storage_dir: str | None = None
    remote_gateway_host: str = "127.0.0.1"
    vnc_gateway_host: str | None = None
    default_vnc_password: str | None = None
    ssh_password: str | None = None
    ssh_key_filename: str | None = None
    ssh_key_passphrase: str | None = None
    ssh_known_hosts_file: str | None = None
    ssh_host_key_policy: str = "auto_add"
    scheduler_enabled: bool = True
    scheduler_poll_interval_seconds: int = 30
    file_backend: str = "sftp"
    default_device_ssh_user: str = "ztl"
    default_device_ssh_password: str = "123456"
    credential_encryption_key: str | None = None
    webhook_timeout_seconds: int = 5
    webhook_max_retries: int = 3
    notification_retention_days: int = 90
    bootstrap_platform_url: str | None = None
    bootstrap_ca_certificate: str | None = None
    bootstrap_ca_cert_path: str | None = None
    bootstrap_frp_server_addr: str | None = None
    bootstrap_frp_server_port: int = 7000
    bootstrap_frp_auth_token: str | None = None
    bootstrap_frpc_download_url: str | None = None
    bootstrap_frpc_sha256: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./data/platform.db"),
        jwt_secret_key=os.getenv("JWT_SECRET_KEY", "change-me-in-production"),
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
        refresh_token_expire_minutes=int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", str(60 * 24))),
        default_admin_username=os.getenv("DEFAULT_ADMIN_USERNAME", "admin"),
        default_admin_password=os.getenv("DEFAULT_ADMIN_PASSWORD", "admin"),
        remote_gateway_host=os.getenv("REMOTE_GATEWAY_HOST", "127.0.0.1"),
        vnc_gateway_host=os.getenv("VNC_GATEWAY_HOST"),
        default_vnc_password=os.getenv("DEFAULT_VNC_PASSWORD"),
        ssh_timeout_seconds=int(os.getenv("SSH_TIMEOUT_SECONDS", "10")),
        vnc_timeout_seconds=int(os.getenv("VNC_TIMEOUT_SECONDS", "10")),
        ssh_password=os.getenv("SSH_PASSWORD"),
        ssh_key_filename=os.getenv("SSH_KEY_FILENAME"),
        ssh_key_passphrase=os.getenv("SSH_KEY_PASSPHRASE"),
        ssh_known_hosts_file=os.getenv("SSH_KNOWN_HOSTS_FILE"),
        ssh_host_key_policy=os.getenv("SSH_HOST_KEY_POLICY", "auto_add"),
        scheduler_enabled=os.getenv("SCHEDULER_ENABLED", "true").lower() not in {"0", "false", "no", "off"},
        scheduler_poll_interval_seconds=int(os.getenv("SCHEDULER_POLL_INTERVAL_SECONDS", "30")),
        file_backend=os.getenv("FILE_BACKEND", "sftp"),
        file_storage_dir=os.getenv("FILE_STORAGE_DIR"),
        default_device_ssh_user=os.getenv("DEFAULT_DEVICE_SSH_USER", "ztl"),
        default_device_ssh_password=os.getenv("DEFAULT_DEVICE_SSH_PASSWORD", "123456"),
        credential_encryption_key=os.getenv("CREDENTIAL_ENCRYPTION_KEY"),
        webhook_timeout_seconds=int(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "5")),
        webhook_max_retries=int(os.getenv("WEBHOOK_MAX_RETRIES", "3")),
        notification_retention_days=int(os.getenv("NOTIFICATION_RETENTION_DAYS", "90")),
        bootstrap_platform_url=os.getenv("BOOTSTRAP_PLATFORM_URL"),
        bootstrap_ca_certificate=(os.getenv("BOOTSTRAP_CA_CERTIFICATE") or "").replace("\\n", "\n") or None,
        bootstrap_ca_cert_path=os.getenv("BOOTSTRAP_CA_CERT_PATH"),
        bootstrap_frp_server_addr=os.getenv("BOOTSTRAP_FRP_SERVER_ADDR"),
        bootstrap_frp_server_port=int(os.getenv("BOOTSTRAP_FRP_SERVER_PORT", "7000")),
        bootstrap_frp_auth_token=os.getenv("BOOTSTRAP_FRP_AUTH_TOKEN"),
        bootstrap_frpc_download_url=os.getenv("BOOTSTRAP_FRPC_DOWNLOAD_URL"),
        bootstrap_frpc_sha256=os.getenv("BOOTSTRAP_FRPC_SHA256"),
    )
