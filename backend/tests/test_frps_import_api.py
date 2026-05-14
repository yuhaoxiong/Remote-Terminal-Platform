from app.database import session_scope
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


def _payload() -> dict[str, object]:
    return {
        "dashboard_url": "124.70.177.226:7500",
        "username": "admin",
        "password": "admin",
        "ssh_port_start": 12001,
        "ssh_port_end": 17000,
        "vnc_port_start": 17001,
        "vnc_port_end": 22000,
        "project_id": "frps-existing",
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


def test_frps_import_creates_devices_and_reserves_existing_ports(client, initialized_settings) -> None:
    client.app.state.frps_dashboard_client = FakeFrpsDashboardClient()
    headers = _auth_headers(client)

    first = client.post("/api/frps/import", headers=headers, json=_payload())
    assert first.status_code == 200
    assert first.json()["created"] == 2
    assert first.json()["skipped"] == 0

    listed = client.get("/api/devices?project_id=frps-existing", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert listed.json()["items"][0]["ssh_port"] == 12008
    assert listed.json()["items"][0]["vnc_port"] == 17008
    assert listed.json()["items"][1]["ssh_port"] == 12009
    assert listed.json()["items"][1]["vnc_port"] is None

    with session_scope(initialized_settings) as session:
        reserved = {
            row.port: row.status
            for row in session.query(PortPool).filter(PortPool.port.in_([12008, 17008, 12009])).all()
        }
    assert reserved == {12008: "allocated", 17008: "allocated", 12009: "allocated"}

    second = client.post("/api/frps/import", headers=headers, json=_payload())
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert second.json()["skipped"] == 2


def test_frps_import_requires_authentication(client) -> None:
    response = client.post("/api/frps/discover", json=_payload())

    assert response.status_code == 403
