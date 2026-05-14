from app.models.device import Device


class FrpcConfigService:
    def generate(self, device: Device) -> str:
        if device.ssh_port is None or device.vnc_port is None:
            raise ValueError("Device must have allocated SSH and VNC ports before frpc config generation")

        return "\n".join(
            [
                f"[{device.device_sn}-ssh]",
                "type = tcp",
                "local_ip = 127.0.0.1",
                "local_port = 22",
                f"remote_port = {device.ssh_port}",
                "",
                f"[{device.device_sn}-vnc]",
                "type = tcp",
                "local_ip = 127.0.0.1",
                "local_port = 5901",
                f"remote_port = {device.vnc_port}",
                "",
            ]
        )

