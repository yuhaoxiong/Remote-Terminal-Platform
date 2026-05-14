from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import init_db
from app.models.port_pool import PortPool


class PortPoolExhaustedError(RuntimeError):
    pass


class PortPoolService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def initialize(self) -> None:
        init_db(self.settings)

    def allocate(self, session: Session, service_type: str, device_id: int) -> int:
        port_record = session.scalar(
            select(PortPool)
            .where(PortPool.service_type == service_type, PortPool.status == "available")
            .order_by(PortPool.port.asc())
            .limit(1)
        )
        if port_record is None:
            raise PortPoolExhaustedError(f"No available {service_type} ports")

        port_record.status = "allocated"
        port_record.device_id = device_id
        port_record.allocated_at = datetime.now(timezone.utc)
        session.flush()
        return port_record.port

    def release(self, session: Session, port: int) -> None:
        port_record = session.scalar(select(PortPool).where(PortPool.port == port))
        if port_record is None:
            return
        port_record.status = "available"
        port_record.device_id = None
        port_record.allocated_at = None
        session.flush()
