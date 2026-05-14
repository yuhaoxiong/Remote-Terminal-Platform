from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceUpdate
from app.services.port_pool import PortPoolService


class DeviceDuplicateError(RuntimeError):
    pass


class DeviceNotFoundError(RuntimeError):
    pass


class DeviceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.port_pool = PortPoolService(settings)

    def create(self, session: Session, payload: DeviceCreate) -> Device:
        existing_id = session.scalar(select(Device.id).where(Device.device_sn == payload.device_sn))
        if existing_id is not None:
            raise DeviceDuplicateError(f"Device SN already exists: {payload.device_sn}")

        values = payload.model_dump()
        ssh_password = values.pop("ssh_password", None)
        device = Device(**values)
        if ssh_password:
            device.ssh_password_encrypted = ssh_password
        session.add(device)
        session.flush()
        device.ssh_port = self.port_pool.allocate(session, "ssh", device.id)
        device.vnc_port = self.port_pool.allocate(session, "vnc", device.id)
        session.flush()
        session.refresh(device)
        return device

    def list(
        self,
        session: Session,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        project_id: str | None = None,
        group_id: int | None = None,
        tag: str | None = None,
        status: str | None = None,
    ) -> tuple[int, list[Device]]:
        statement = select(Device)
        count_statement = select(func.count(Device.id))
        if search:
            pattern = f"%{search}%"
            statement = statement.where(Device.name.like(pattern) | Device.device_sn.like(pattern))
            count_statement = count_statement.where(Device.name.like(pattern) | Device.device_sn.like(pattern))
        if project_id:
            statement = statement.where(Device.project_id == project_id)
            count_statement = count_statement.where(Device.project_id == project_id)
        if group_id is not None:
            statement = statement.where(Device.group_id == group_id)
            count_statement = count_statement.where(Device.group_id == group_id)
        if status:
            statement = statement.where(Device.status == status)
            count_statement = count_statement.where(Device.status == status)

        all_devices = list(session.scalars(statement.order_by(Device.id.asc())))
        if tag:
            all_devices = [device for device in all_devices if tag in (device.tags or [])]
        total = len(all_devices) if tag else session.scalar(count_statement) or 0
        devices = all_devices[offset : offset + limit] if tag else list(session.scalars(statement.order_by(Device.id.asc()).offset(offset).limit(limit)))
        return total, devices

    def get(self, session: Session, device_id: int) -> Device:
        device = session.get(Device, device_id)
        if device is None:
            raise DeviceNotFoundError(f"Device not found: {device_id}")
        return device

    def update(self, session: Session, device_id: int, payload: DeviceUpdate) -> Device:
        device = self.get(session, device_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            if field == "ssh_password":
                if value:
                    device.ssh_password_encrypted = value
                continue
            setattr(device, field, value)
        session.flush()
        session.refresh(device)
        return device

    def delete(self, session: Session, device_id: int) -> None:
        device = self.get(session, device_id)
        if device.ssh_port is not None:
            self.port_pool.release(session, device.ssh_port)
        if device.vnc_port is not None:
            self.port_pool.release(session, device.vnc_port)
        session.delete(device)
        session.flush()
