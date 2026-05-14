from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PortPool(Base):
    __tablename__ = "port_pool"
    __table_args__ = (UniqueConstraint("service_type", "port", name="uq_port_pool_service_port"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    service_type: Mapped[str] = mapped_column(String(16), index=True)
    port: Mapped[int] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(32), default="available", index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    allocated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
