from app.database import session_scope
from app.models.device import Device
from app.models.port_pool import PortPool


class FakeFrpsDashboardClient:
    def fetch_tcp_proxies(self, payload):
        return [
            {"name": "ssh-12008", "conf": {"remotePort": 12008}, "status": "online"},
            {"name": "vnc-17008", "conf": {"remotePort": 17008}, "status": "online"},
            {"name": "ssh-12009", "conf": {"remotePort": 12009}, "status": "online"},
            {"name": "unrelated", "conf": {"remotePort": 25000}, "status": "online"},
        ]


def _auth_headers(client) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _operator_headers(client) -> dict[str, str]:
    admin_headers = _auth_headers(client)
    created = client.post(
        "/api/users",
        headers=admin_headers,
        json={"username": "frps-operator", "password": "operator-pass", "role": "operator", "is_active": True},
    )
    assert created.status_code == 201
    response = client.post("/api/auth/login", json={"username": "frps-operator", "password": "operator-pass"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _payload(project_id: int | None = None) -> dict[str, object]:
    return {
        "dashboard_url": "124.70.177.226:7500",
        "username": "admin",
        "password": "admin",
        "ssh_port_start": 12001,
        "ssh_port_end": 17000,
        "vnc_port_start": 17001,
        "vnc_port_end": 22000,
        "project_id": project_id,
    }


def test_frps_discover_previews_tcp_proxies_by_port_pairing(client) -> None:
    client.app.state.frps_dashboard_client = FakeFrpsDashboardClient()
    headers = _auth_headers(client)

    response = client.post("/api/frps/discover", headers=headers, json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["created"] == 0
    assert body["items"][0]["ssh_port"] == 12008
    assert body["items"][0]["vnc_port"] == 17008
    assert body["items"][1]["ssh_port"] == 12009
    assert body["items"][1]["vnc_port"] is None
    assert "17009" in body["items"][1]["detail"]
    assert body["items"][1]["import_status"] == "missing_vnc"


def test_frps_import_creates_devices_and_reserves_existing_ports(client, initialized_settings, create_project) -> None:
    client.app.state.frps_dashboard_client = FakeFrpsDashboardClient()
    headers = _auth_headers(client)
    project = create_project("frps-existing")

    first = client.post("/api/frps/import", headers=headers, json=_payload(project.id))
    assert first.status_code == 200
    assert first.json()["created"] == 2
    assert first.json()["skipped"] == 0

    listed = client.get(f"/api/devices?project_id={project.id}", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert listed.json()["items"][0]["ssh_port"] == 12008
    assert listed.json()["items"][0]["vnc_port"] == 17008
    assert listed.json()["items"][0]["ssh_user"] == "ztl"
    assert listed.json()["items"][0]["ssh_credential_configured"] is True
    assert "123456" not in str(listed.json())
    assert listed.json()["items"][1]["ssh_port"] == 12009
    assert listed.json()["items"][1]["vnc_port"] is None

    with session_scope(initialized_settings) as session:
        reserved = {
            row.port: row.status
            for row in session.query(PortPool).filter(PortPool.port.in_([12008, 17008, 12009])).all()
        }
    assert reserved == {12008: "allocated", 17008: "allocated", 12009: "allocated"}

    second = client.post("/api/frps/import", headers=headers, json=_payload(project.id))
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert second.json()["synced"] == 2


def test_frps_import_reports_conflict_and_respects_project_location_overwrite(client, initialized_settings, create_project) -> None:
    client.app.state.frps_dashboard_client = FakeFrpsDashboardClient()
    headers = _auth_headers(client)
    existing_project = create_project("frps-existing")
    manual_project = create_project("manual-project")
    new_project = create_project("new-project")

    with session_scope(initialized_settings) as session:
        device = Device(
            name="manual",
            device_sn="manual-12008",
            project_id=manual_project.id,
            location="manual-location",
            ssh_port=12008,
            ssh_user="custom",
            ssh_auth_type="password",
            ssh_password_encrypted="custom-pass",
        )
        session.add(device)

    preview = client.post("/api/frps/discover", headers=headers, json=_payload(existing_project.id))
    assert preview.status_code == 200
    assert preview.json()["items"][0]["import_status"] == "conflict"
    assert preview.json()["conflicts"] == 1

    with session_scope(initialized_settings) as session:
        session.query(Device).filter(Device.device_sn == "manual-12008").delete()

    imported = client.post("/api/frps/import", headers=headers, json=_payload(existing_project.id))
    assert imported.status_code == 200

    no_overwrite = client.post(
        "/api/frps/import",
        headers=headers,
        json={**_payload(new_project.id), "location": "new-location"},
    )
    assert no_overwrite.status_code == 200
    with session_scope(initialized_settings) as session:
        existing = session.query(Device).filter(Device.device_sn == "frps-12008").one()
        assert existing.project_id == existing_project.id
        assert existing.location == "frps"
        assert existing.ssh_user == "ztl"

    overwrite = client.post(
        "/api/frps/import",
        headers=headers,
        json={**_payload(new_project.id), "location": "new-location", "overwrite_project_location": True},
    )
    assert overwrite.status_code == 200
    with session_scope(initialized_settings) as session:
        existing = session.query(Device).filter(Device.device_sn == "frps-12008").one()
        assert existing.project_id == new_project.id
        assert existing.location == "new-location"
        assert existing.ssh_user == "ztl"
        assert existing.ssh_password_encrypted == "123456"


def test_frps_import_requires_authentication(client) -> None:
    response = client.post("/api/frps/discover", json=_payload())

    assert response.status_code == 403


def test_frps_import_requires_admin_role(client) -> None:
    client.app.state.frps_dashboard_client = FakeFrpsDashboardClient()
    headers = _operator_headers(client)

    preview = client.post("/api/frps/discover", headers=headers, json=_payload())
    imported = client.post("/api/frps/import", headers=headers, json=_payload())

    assert preview.status_code == 403
    assert imported.status_code == 403
