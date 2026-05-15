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
    ssh_password: str | None = None
    ssh_key_filename: str | None = None
    ssh_key_passphrase: str | None = None
    file_backend: str = "local"
    default_device_ssh_user: str = "ztl"
    default_device_ssh_password: str = "123456"
    credential_encryption_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings(
        jwt_secret_key=os.getenv("JWT_SECRET_KEY", "change-me-in-production"),
        default_admin_username=os.getenv("DEFAULT_ADMIN_USERNAME", "admin"),
        default_admin_password=os.getenv("DEFAULT_ADMIN_PASSWORD", "admin"),
        remote_gateway_host=os.getenv("REMOTE_GATEWAY_HOST", "127.0.0.1"),
        vnc_gateway_host=os.getenv("VNC_GATEWAY_HOST"),
        ssh_password=os.getenv("SSH_PASSWORD"),
        ssh_key_filename=os.getenv("SSH_KEY_FILENAME"),
        ssh_key_passphrase=os.getenv("SSH_KEY_PASSPHRASE"),
        file_backend=os.getenv("FILE_BACKEND", "local"),
        default_device_ssh_user=os.getenv("DEFAULT_DEVICE_SSH_USER", "ztl"),
        default_device_ssh_password=os.getenv("DEFAULT_DEVICE_SSH_PASSWORD", "123456"),
        credential_encryption_key=os.getenv("CREDENTIAL_ENCRYPTION_KEY"),
    )
