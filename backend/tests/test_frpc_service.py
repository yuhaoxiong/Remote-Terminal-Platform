from app.models.device import Device
from app.services.frpc_config import FrpcConfigService


def test_frpc_config_generation_includes_ssh_and_vnc_proxies() -> None:
    device = Device(
        id=7,
        name="Edge box",
        device_sn="edge-sn-007",
        project_id=None,
        ssh_user="root",
        ssh_port=10007,
        vnc_port=10507,
    )

    config = FrpcConfigService().generate(device)

    assert "[edge-sn-007-ssh]" in config
    assert "type = tcp" in config
    assert "local_port = 22" in config
    assert "remote_port = 10007" in config
    assert "[edge-sn-007-vnc]" in config
    assert "local_port = 5901" in config
    assert "remote_port = 10507" in config
