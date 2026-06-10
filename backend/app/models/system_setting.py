from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    value_type: Mapped[str] = mapped_column(String(32))
    value_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    secret_value_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="database", index=True)
    is_secret: Mapped[bool] = mapped_column(default=False)
    requires_restart: Mapped[bool] = mapped_column(default=False, index=True)
    pending_restart: Mapped[bool] = mapped_column(default=False, index=True)
    is_valid: Mapped[bool] = mapped_column(default=True, index=True)
    invalid_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class SystemSettingChange(Base):
    __tablename__ = "system_setting_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    setting_key: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    old_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    old_value_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(default=False)
    requires_restart: Mapped[bool] = mapped_column(default=False)
    pending_restart_after_change: Mapped[bool] = mapped_column(default=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
