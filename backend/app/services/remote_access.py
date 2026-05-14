from app.models.device import Device


class RemoteAccessService:
    def build_ssh_session(self, device: Device) -> dict[str, object]:
        if device.ssh_port is None:
            raise ValueError("Device does not have an allocated SSH port")
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
            raise ValueError("Device does not have an allocated VNC port")
        return {
            "device_id": device.id,
            "session_type": "vnc",
            "status": "ready",
            "remote_port": device.vnc_port,
            "websocket_url": f"/api/ws/devices/{device.id}/vnc",
            "proxy_url": f"/novnc/vnc.html?device_id={device.id}&port={device.vnc_port}",
        }
