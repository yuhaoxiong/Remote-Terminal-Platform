def _auth(client) -> tuple[dict[str, str], str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-pass"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, token


def _device_payload(device_sn: str, *, project_id: int, tags: list[str]) -> dict[str, object]:
    return {
        "name": f"Device {device_sn}",
        "device_sn": device_sn,
        "project_id": project_id,
        "location": "Line 1",
        "hardware_model": "IPC-3000",
        "ssh_user": "root",
        "local_ip": "192.168.10.21",
        "tags": tags,
    }


def test_update_task_lifecycle_filters_targets_and_streams_progress(client, create_project) -> None:
    headers, token = _auth(client)
    project_a = create_project("factory-a")
    project_b = create_project("factory-b")
    first = client.post(
        "/api/devices",
        headers=headers,
        json=_device_payload("edge-update-001", project_id=project_a.id, tags=["vision", "prod"]),
    )
    assert first.status_code == 201
    second = client.post(
        "/api/devices",
        headers=headers,
        json=_device_payload("edge-update-002", project_id=project_b.id, tags=["vision"]),
    )
    assert second.status_code == 201

    missing_rollback = client.post(
        "/api/update-tasks",
        headers=headers,
        json={
            "name": "Config rollback required",
            "task_type": "config",
            "command": "sudo systemctl restart ai-app",
            "target_filter": {"project_id": project_a.id},
            "failure_strategy": "rollback",
        },
    )
    assert missing_rollback.status_code == 422

    created = client.post(
        "/api/update-tasks",
        headers=headers,
        json={
            "name": "Restart factory A",
            "task_type": "script",
            "command": "sudo systemctl restart ai-app",
            "target_filter": {"project_id": project_a.id, "tags": ["vision"]},
            "failure_strategy": "continue",
            "concurrency_limit": 2,
        },
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert created.json()["status"] == "pending"
    assert created.json()["device_count"] == 1
    assert created.json()["devices"][0]["device_id"] == first.json()["id"]

    listed = client.get("/api/update-tasks?status=pending", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    executed = client.post(f"/api/update-tasks/{task_id}/execute", headers=headers)
    assert executed.status_code == 200
    assert executed.json()["status"] == "completed"
    assert executed.json()["execution_mode"] == "dry_run"
    assert executed.json()["devices"][0]["status"] == "skipped"
    assert "sudo systemctl restart ai-app" in executed.json()["devices"][0]["output_summary"]

    detail = client.get(f"/api/update-tasks/{task_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "completed"

    with client.websocket_connect(f"/api/ws/update-tasks/{task_id}?token={token}") as websocket:
        snapshot = websocket.receive_json()
    assert snapshot["type"] == "task.snapshot"
    assert snapshot["task"]["status"] == "completed"
    assert snapshot["task"]["devices"][0]["status"] == "skipped"
    assert "exit_code" in snapshot["task"]["devices"][0]


def test_update_task_cancel_marks_pending_devices(client, create_project) -> None:
    headers, _token = _auth(client)
    project = create_project("factory-c")
    device = client.post(
        "/api/devices",
        headers=headers,
        json=_device_payload("edge-update-003", project_id=project.id, tags=["prod"]),
    )
    assert device.status_code == 201

    created = client.post(
        "/api/update-tasks",
        headers=headers,
        json={
            "name": "Cancel pending task",
            "task_type": "script",
            "command": "echo later",
            "target_filter": {"project_id": project.id},
        },
    )
    assert created.status_code == 201

    canceled = client.post(f"/api/update-tasks/{created.json()['id']}/cancel", headers=headers)
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"
    assert canceled.json()["devices"][0]["status"] == "canceled"
