def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-pass"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_device(client, headers: dict[str, str], device_sn: str = "monitor-sn-001") -> dict:
    response = client.post(
        "/api/devices",
        headers=headers,
        json={
            "name": "Monitoring edge box",
            "device_sn": device_sn,
            "project_id": "factory-a",
            "ssh_user": "root",
            "local_ip": "192.168.20.10",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_device_metrics_update_status_and_overview(client) -> None:
    headers = _auth_headers(client)
    device = _create_device(client, headers)

    metric_response = client.post(
        f"/api/devices/{device['id']}/metrics",
        headers=headers,
        json={
            "status": "online",
            "cpu_percent": 23.5,
            "memory_percent": 51.0,
            "disk_percent": 66.0,
            "temperature_celsius": 42.3,
            "load_average": 0.75,
        },
    )
    assert metric_response.status_code == 201
    metric_body = metric_response.json()
    assert metric_body["device_id"] == device["id"]
    assert metric_body["status"] == "online"
    assert metric_body["cpu_percent"] == 23.5
    assert metric_body["recorded_at"]

    status_response = client.get(f"/api/devices/{device['id']}/status", headers=headers)
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "online"
    assert status_response.json()["last_seen"]

    metrics_response = client.get(f"/api/devices/{device['id']}/metrics", headers=headers)
    assert metrics_response.status_code == 200
    metrics_body = metrics_response.json()
    assert metrics_body["total"] == 1
    assert metrics_body["items"][0]["memory_percent"] == 51.0

    overview_response = client.get("/api/monitoring/overview", headers=headers)
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["total_devices"] == 1
    assert overview["online_devices"] == 1
    assert overview["offline_devices"] == 0
    assert overview["unknown_devices"] == 0


def test_metrics_reject_missing_device_and_authentication(client) -> None:
    no_auth = client.post("/api/devices/1/metrics", json={"status": "online"})
    assert no_auth.status_code == 403

    headers = _auth_headers(client)
    missing = client.post("/api/devices/999/metrics", headers=headers, json={"status": "online"})
    assert missing.status_code == 404


def test_metrics_list_returns_latest_limited_empty_and_missing_device(client) -> None:
    headers = _auth_headers(client)
    device = _create_device(client, headers, device_sn="monitor-sn-002")

    empty_response = client.get(f"/api/devices/{device['id']}/metrics?limit=1", headers=headers)
    assert empty_response.status_code == 200
    assert empty_response.json() == {"total": 0, "items": []}

    first = client.post(
        f"/api/devices/{device['id']}/metrics",
        headers=headers,
        json={"status": "online", "cpu_percent": 11.0, "memory_percent": 22.0, "disk_percent": 33.0},
    )
    assert first.status_code == 201
    second = client.post(
        f"/api/devices/{device['id']}/metrics",
        headers=headers,
        json={"status": "online", "cpu_percent": 91.0, "memory_percent": 88.0, "disk_percent": 77.0},
    )
    assert second.status_code == 201

    latest_response = client.get(f"/api/devices/{device['id']}/metrics?limit=1", headers=headers)
    assert latest_response.status_code == 200
    latest_body = latest_response.json()
    assert latest_body["total"] == 2
    assert len(latest_body["items"]) == 1
    assert latest_body["items"][0]["cpu_percent"] == 91.0

    missing_response = client.get("/api/devices/999/metrics?limit=1", headers=headers)
    assert missing_response.status_code == 404
