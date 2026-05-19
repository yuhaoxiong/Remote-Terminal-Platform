from app.database import session_scope
from app.models.device import Device


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-pass"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_device(client, headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/devices",
        headers=headers,
        json={
            "name": "Remote edge box",
            "device_sn": "remote-sn-001",
            "project_id": "factory-a",
            "ssh_user": "root",
            "local_ip": "192.168.30.10",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_remote_access_sessions_expose_webssh_and_vnc_proxy_descriptors(client) -> None:
    headers = _auth_headers(client)
    device = _create_device(client, headers)

    ssh_response = client.post(f"/api/devices/{device['id']}/remote/ssh", headers=headers)
    assert ssh_response.status_code == 200
    ssh = ssh_response.json()
    assert ssh["device_id"] == device["id"]
    assert ssh["session_type"] == "ssh"
    assert ssh["status"] == "ready"
    assert ssh["remote_port"] == 10000
    assert ssh["websocket_url"] == f"/api/ws/devices/{device['id']}/ssh"

    vnc_response = client.post(f"/api/devices/{device['id']}/remote/vnc", headers=headers)
    assert vnc_response.status_code == 200
    vnc = vnc_response.json()
    assert vnc["device_id"] == device["id"]
    assert vnc["session_type"] == "vnc"
    assert vnc["status"] == "ready"
    assert vnc["remote_port"] == 10500
    assert f"device_id={device['id']}" in vnc["proxy_url"]
    assert "port=10500" in vnc["proxy_url"]


def test_remote_access_requires_authentication_and_existing_device(client) -> None:
    no_auth = client.post("/api/devices/1/remote/ssh")
    assert no_auth.status_code == 403

    headers = _auth_headers(client)
    missing = client.post("/api/devices/999/remote/vnc", headers=headers)
    assert missing.status_code == 404


def test_remote_access_reports_missing_ports_and_credentials(client, initialized_settings) -> None:
    headers = _auth_headers(client)
    device = _create_device(client, headers)

    with session_scope(initialized_settings) as session:
        stored = session.get(Device, device["id"])
        assert stored is not None
        stored.ssh_port = None
        stored.vnc_port = None
        stored.ssh_password_encrypted = None

    ssh_response = client.post(f"/api/devices/{device['id']}/remote/ssh", headers=headers)
    assert ssh_response.status_code == 400
    assert ssh_response.json()["detail"] == "设备没有分配 SSH 端口"

    vnc_response = client.post(f"/api/devices/{device['id']}/remote/vnc", headers=headers)
    assert vnc_response.status_code == 400
    assert vnc_response.json()["detail"] == "设备没有分配 VNC 端口"

    with session_scope(initialized_settings) as session:
        stored = session.get(Device, device["id"])
        assert stored is not None
        stored.ssh_port = 16001
        stored.ssh_password_encrypted = None
        stored.ssh_key_encrypted = None

    credential_response = client.post(f"/api/devices/{device['id']}/remote/ssh", headers=headers)
    assert credential_response.status_code == 400
    assert credential_response.json()["detail"] == "设备没有可用的 SSH 凭据"
