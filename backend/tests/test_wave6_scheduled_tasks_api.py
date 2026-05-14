def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-pass"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_scheduled_task_crud_toggle_execute_and_logs(client) -> None:
    headers = _auth_headers(client)

    created = client.post(
        "/api/scheduled-tasks",
        headers=headers,
        json={
            "name": "Nightly health check",
            "task_type": "health_check",
            "schedule": "cron:0 2 * * *",
            "command": "echo ok",
            "target_filter": {"project_id": "factory-a"},
        },
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert created.json()["enabled"] is True

    listed = client.get("/api/scheduled-tasks", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    updated = client.put(
        f"/api/scheduled-tasks/{task_id}",
        headers=headers,
        json={"schedule": "interval:60", "enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["schedule"] == "interval:60"
    assert updated.json()["enabled"] is False

    toggled = client.post(f"/api/scheduled-tasks/{task_id}/toggle", headers=headers)
    assert toggled.status_code == 200
    assert toggled.json()["enabled"] is True

    executed = client.post(f"/api/scheduled-tasks/{task_id}/execute", headers=headers)
    assert executed.status_code == 200
    assert executed.json()["status"] == "success"

    logs = client.get(f"/api/scheduled-tasks/{task_id}/logs", headers=headers)
    assert logs.status_code == 200
    assert logs.json()["total"] >= 1
    assert logs.json()["items"][0]["action"] == "scheduled_task.execute"

    deleted = client.delete(f"/api/scheduled-tasks/{task_id}", headers=headers)
    assert deleted.status_code == 204


def test_scheduled_task_requires_supported_schedule_prefix(client) -> None:
    headers = _auth_headers(client)

    response = client.post(
        "/api/scheduled-tasks",
        headers=headers,
        json={
            "name": "Invalid schedule",
            "task_type": "command",
            "schedule": "tomorrow maybe",
            "command": "echo ok",
        },
    )

    assert response.status_code == 422
