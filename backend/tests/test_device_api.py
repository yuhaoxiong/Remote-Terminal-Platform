from app.database import session_scope
from app.models.port_pool import PortPool


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-pass"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _device_payload(device_sn: str = "edge-sn-001") -> dict[str, object]:
    return {
        "name": "Assembly line edge box",
        "device_sn": device_sn,
        "project_id": "factory-a",
        "location": "Line 1",
        "hardware_model": "IPC-3000",
        "ssh_user": "root",
        "local_ip": "192.168.10.21",
        "description": "AI inspection terminal",
        "tags": ["vision", "production"],
    }


def test_device_crud_allocates_ports_and_releases_them(client, initialized_settings) -> None:
    headers = _auth_headers(client)

    created = client.post("/api/devices", headers=headers, json=_device_payload())
    assert created.status_code == 201
    created_body = created.json()
    assert created_body["id"] > 0
    assert created_body["device_sn"] == "edge-sn-001"
    assert created_body["ssh_port"] == 10000
    assert created_body["vnc_port"] == 10500
    assert created_body["ssh_user"] == "root"
    assert created_body["ssh_auth_type"] == "password"
    assert created_body["ssh_credential_configured"] is True
    assert "ssh_password" not in created_body
    assert "ssh_password_encrypted" not in created_body
    assert created_body["status"] == "unknown"

    duplicate = client.post("/api/devices", headers=headers, json=_device_payload())
    assert duplicate.status_code == 409

    listed = client.get("/api/devices", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["device_sn"] == "edge-sn-001"

    detail = client.get(f"/api/devices/{created_body['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["ssh_port"] == 10000

    updated = client.put(
        f"/api/devices/{created_body['id']}",
        headers=headers,
        json={"name": "Updated edge box", "status": "online", "tags": ["vision"], "ssh_password": "new-pass"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated edge box"
    assert updated.json()["status"] == "online"
    assert updated.json()["ssh_credential_configured"] is True
    assert "new-pass" not in str(updated.json())

    sync_response = client.post(f"/api/devices/{created_body['id']}/sync-config", headers=headers)
    assert sync_response.status_code == 200
    sync_body = sync_response.json()
    assert sync_body["status"] == "generated"
    assert "[edge-sn-001-ssh]" in sync_body["config"]
    assert "remote_port = 10000" in sync_body["config"]
    assert "[edge-sn-001-vnc]" in sync_body["config"]
    assert "remote_port = 10500" in sync_body["config"]

    deleted = client.delete(f"/api/devices/{created_body['id']}", headers=headers)
    assert deleted.status_code == 204

    with session_scope(initialized_settings) as session:
        released_ports = {
            row.port: row.status
            for row in session.query(PortPool).filter(PortPool.port.in_([10000, 10500])).all()
        }
    assert released_ports == {10000: "available", 10500: "available"}

    recreated = client.post("/api/devices", headers=headers, json=_device_payload("edge-sn-002"))
    assert recreated.status_code == 201
    assert recreated.json()["ssh_port"] == 10000
    assert recreated.json()["vnc_port"] == 10500


def test_device_endpoints_require_authentication(client) -> None:
    response = client.get("/api/devices")

    assert response.status_code == 403
