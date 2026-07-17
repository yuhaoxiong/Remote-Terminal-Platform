from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=lambda: str(uuid4()),
    )
    name: Mapped[str] = mapped_column(String(120), index=True)
    device_sn: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True, nullable=True)
    expected_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("hardware_profiles.id"),
        index=True,
        nullable=True,
    )
    actual_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("hardware_profiles.id"),
        index=True,
        nullable=True,
    )
    device_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_test_device: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hardware_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ssh_port: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    vnc_port: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    ssh_user: Mapped[str] = mapped_column(String(64), default="ztl")
    ssh_auth_type: Mapped[str] = mapped_column(String(32), default="password")
    ssh_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssh_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def ssh_credential_configured(self) -> bool:
        return bool(self.ssh_password_encrypted or self.ssh_key_encrypted)
