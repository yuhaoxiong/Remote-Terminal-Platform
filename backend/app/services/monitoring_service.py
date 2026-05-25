from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.device import Device
from app.models.metric import DeviceMetric
from app.schemas.device import DeviceMetricCreate
from app.services.alert_service import AlertService
from app.services.device_service import DeviceNotFoundError


class MonitoringService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def record_metric(self, session: Session, device_id: int, payload: DeviceMetricCreate) -> tuple[Device, DeviceMetric]:
        device = session.get(Device, device_id)
        if device is None:
            raise DeviceNotFoundError(f"Device not found: {device_id}")

        device.status = payload.status
        device.last_seen = datetime.now(timezone.utc)
        metric = DeviceMetric(
            device_id=device.id,
            cpu_percent=payload.cpu_percent,
            memory_percent=payload.memory_percent,
            disk_percent=payload.disk_percent,
            temperature_celsius=payload.temperature_celsius,
            load_average=payload.load_average,
        )
        session.add(metric)
        session.flush()
        AlertService(self.settings).evaluate_device_metrics(session, device, metric)
        session.refresh(metric)
        session.refresh(device)
        return device, metric

    def list_metrics(self, session: Session, device_id: int, *, limit: int) -> tuple[int, list[DeviceMetric]]:
        if session.get(Device, device_id) is None:
            raise DeviceNotFoundError(f"Device not found: {device_id}")

        total = session.scalar(select(func.count(DeviceMetric.id)).where(DeviceMetric.device_id == device_id)) or 0
        metrics = list(
            session.scalars(
                select(DeviceMetric)
                .where(DeviceMetric.device_id == device_id)
                .order_by(DeviceMetric.recorded_at.desc(), DeviceMetric.id.desc())
                .limit(limit)
            )
        )
        return total, metrics

    def overview(self, session: Session) -> dict[str, int]:
        total = session.scalar(select(func.count(Device.id))) or 0
        online = session.scalar(select(func.count(Device.id)).where(Device.status == "online")) or 0
        offline = session.scalar(select(func.count(Device.id)).where(Device.status == "offline")) or 0
        unknown = total - online - offline
        return {
            "total_devices": total,
            "online_devices": online,
            "offline_devices": offline,
            "unknown_devices": unknown,
        }
