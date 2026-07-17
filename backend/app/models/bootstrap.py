from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DeviceBootstrapPackage(Base):
    __tablename__ = "device_bootstrap_packages"
    __table_args__ = (UniqueConstraint("device_id", "generation", name="uq_device_bootstrap_generation"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    generation: Mapped[int]
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    validation_errors: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    token_digest: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    vnc_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    ca_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
