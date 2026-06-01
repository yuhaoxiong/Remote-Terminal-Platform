from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AlertNotificationChannel(Base):
    __tablename__ = "alert_notification_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    channel_type: Mapped[str] = mapped_column(String(32), index=True)
    enabled: Mapped[bool] = mapped_column(default=True, index=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    secret_config_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_test_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AlertNotificationPolicy(Base):
    __tablename__ = "alert_notification_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(default=True, index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("alert_notification_channels.id"), index=True)
    min_severity: Mapped[str] = mapped_column(String(32), default="critical")
    source_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    alert_statuses: Mapped[list[str]] = mapped_column(JSON, default=list)
    event_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AlertNotificationDelivery(Base):
    __tablename__ = "alert_notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "alert_id",
            "channel_id",
            "policy_id",
            "event_type",
            name="uq_alert_notification_delivery_event",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("alert_notification_channels.id"), index=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("alert_notification_policies.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    response_status_code: Mapped[int | None] = mapped_column(nullable=True)
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
