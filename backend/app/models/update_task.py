from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UpdateTask(Base):
    __tablename__ = "update_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    task_type: Mapped[str] = mapped_column(String(32), index=True)
    command: Mapped[str] = mapped_column(Text)
    rollback_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_filter: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    execution_mode: Mapped[str] = mapped_column(String(32), default="dry_run", index=True)
    failure_strategy: Mapped[str] = mapped_column(String(32), default="continue", index=True)
    concurrency_limit: Mapped[int] = mapped_column(default=5)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class UpdateTaskDevice(Base):
    __tablename__ = "update_task_devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("update_tasks.id"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(nullable=True)
    stdout_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
