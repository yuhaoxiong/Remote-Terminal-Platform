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


def test_device_update_changes_remote_port(client) -> None:
    headers = _auth_headers(client)
    created = client.post("/api/devices", headers=headers, json=_device_payload())
    device_id = created.json()["id"]

    updated = client.put(
        f"/api/devices/{device_id}",
        headers=headers,
        json={"ssh_port": 10010},
    )

    assert updated.status_code == 200
    assert updated.json()["ssh_port"] == 10010
    detail = client.get(f"/api/devices/{device_id}", headers=headers)
    assert detail.json()["ssh_port"] == 10010


def test_device_create_reserves_requested_remote_ports(client) -> None:
    headers = _auth_headers(client)
    payload = {
        **_device_payload(),
        "ssh_port": 10010,
        "vnc_port": 10510,
    }

    created = client.post("/api/devices", headers=headers, json=payload)

    assert created.status_code == 201
    assert created.json()["ssh_port"] == 10010
    assert created.json()["vnc_port"] == 10510


def test_device_create_with_null_remote_ports_keeps_auto_allocation(client) -> None:
    headers = _auth_headers(client)

    created = client.post(
        "/api/devices",
        headers=headers,
        json={**_device_payload(), "ssh_port": None, "vnc_port": None},
    )

    assert created.status_code == 201
    assert created.json()["ssh_port"] == 10000
    assert created.json()["vnc_port"] == 10500


def test_device_update_clears_and_reuses_remote_port(client) -> None:
    headers = _auth_headers(client)
    first = client.post("/api/devices", headers=headers, json=_device_payload("edge-sn-001")).json()

    cleared = client.put(
        f"/api/devices/{first['id']}",
        headers=headers,
        json={"ssh_port": None},
    )

    assert cleared.status_code == 200
    assert cleared.json()["ssh_port"] is None
    second = client.post("/api/devices", headers=headers, json=_device_payload("edge-sn-002"))
    assert second.status_code == 201
    assert second.json()["ssh_port"] == first["ssh_port"]


def test_device_update_releases_port_for_the_correct_service_type(client) -> None:
    headers = _auth_headers(client)
    first = client.post(
        "/api/devices",
        headers=headers,
        json={**_device_payload("edge-sn-001"), "ssh_port": 10010, "vnc_port": 10010},
    ).json()

    cleared = client.put(
        f"/api/devices/{first['id']}",
        headers=headers,
        json={"vnc_port": None},
    )
    second = client.post(
        "/api/devices",
        headers=headers,
        json={**_device_payload("edge-sn-002"), "ssh_port": 10011, "vnc_port": 10010},
    )

    assert cleared.status_code == 200
    assert second.status_code == 201
    assert second.json()["vnc_port"] == 10010


def test_device_update_rejects_remote_port_owned_by_another_device(client) -> None:
    headers = _auth_headers(client)
    first = client.post("/api/devices", headers=headers, json=_device_payload("edge-sn-001")).json()
    second = client.post("/api/devices", headers=headers, json=_device_payload("edge-sn-002")).json()

    response = client.put(
        f"/api/devices/{first['id']}",
        headers=headers,
        json={"ssh_port": second["ssh_port"]},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == f"SSH 端口已被其他设备占用：{second['ssh_port']}"
    first_detail = client.get(f"/api/devices/{first['id']}", headers=headers).json()
    second_detail = client.get(f"/api/devices/{second['id']}", headers=headers).json()
    assert first_detail["ssh_port"] == first["ssh_port"]
    assert second_detail["ssh_port"] == second["ssh_port"]


def test_device_update_rolls_back_both_ports_when_one_conflicts(client) -> None:
    headers = _auth_headers(client)
    first = client.post("/api/devices", headers=headers, json=_device_payload("edge-sn-001")).json()
    second = client.post("/api/devices", headers=headers, json=_device_payload("edge-sn-002")).json()

    response = client.put(
        f"/api/devices/{first['id']}",
        headers=headers,
        json={"ssh_port": 10010, "vnc_port": second["vnc_port"]},
    )

    assert response.status_code == 409
    detail = client.get(f"/api/devices/{first['id']}", headers=headers).json()
    assert detail["ssh_port"] == first["ssh_port"]
    assert detail["vnc_port"] == first["vnc_port"]
    third = client.post(
        "/api/devices",
        headers=headers,
        json={**_device_payload("edge-sn-003"), "ssh_port": 10010, "vnc_port": 10510},
    )
    assert third.status_code == 201


def test_device_endpoints_require_authentication(client) -> None:
    response = client.get("/api/devices")

    assert response.status_code == 403
