from app.config import Settings
from app.models.device import Device
from app.services.encryption import EncryptionService


class RemoteAccessService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    def build_ssh_session(self, device: Device) -> dict[str, object]:
        if device.ssh_port is None:
            raise ValueError("设备没有分配 SSH 端口")
        if not device.ssh_password_encrypted:
            raise ValueError("设备没有可用的 SSH 凭据")
        return {
            "device_id": device.id,
            "session_type": "ssh",
            "status": "ready",
            "remote_port": device.ssh_port,
            "websocket_url": f"/api/ws/devices/{device.id}/ssh",
            "proxy_url": None,
        }

    def build_vnc_session(self, device: Device) -> dict[str, object]:
        if device.vnc_port is None:
            raise ValueError("设备没有分配 VNC 端口")
        device_password = None
        if self.settings and device.vnc_password_encrypted:
            device_password = EncryptionService(self.settings).decrypt_optional(device.vnc_password_encrypted)
        return {
            "device_id": device.id,
            "session_type": "vnc",
            "status": "ready",
            "remote_port": device.vnc_port,
            "websocket_url": f"/api/ws/devices/{device.id}/vnc",
            "proxy_url": f"/novnc/vnc.html?device_id={device.id}&port={device.vnc_port}",
            "vnc_password": device_password or (self.settings.default_vnc_password if self.settings else None),
        }
