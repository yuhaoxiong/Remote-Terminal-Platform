from app.migrations import migration_status


def test_wave17_diagnostics_reports_migration_and_ssh_policy(client, auth_headers) -> None:
    response = client.get("/api/diagnostics/config", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["migration"]["current_revision"] == body["migration"]["head_revision"]
    assert body["migration"]["has_pending_migrations"] is False
    assert body["ssh_host_key"]["policy"] == "auto_add"
    assert body["ssh_host_key"]["known_hosts_configured"] is False
    assert body["auth_lifetime"]["access_expire_minutes"] > 0
    assert body["database_status"]["sqlite_backup_recommended"] is True
    assert "password" not in body
    assert "token" not in str(body).lower()


def test_wave17_migration_status_matches_head_after_init(initialized_settings) -> None:
    status = migration_status(initialized_settings)

    assert status.current_revision == status.head_revision
    assert status.has_pending_migrations is False
    assert status.last_error is None


def test_wave17_device_enums_reject_unknown_values(client, auth_headers, create_device) -> None:
    invalid_auth = client.post(
        "/api/devices",
        headers=auth_headers,
        json={
            "name": "bad auth device",
            "device_sn": "bad-auth-001",
            "ssh_auth_type": "agent",
        },
    )
    assert invalid_auth.status_code == 422

    device = create_device()
    invalid_status = client.put(
        f"/api/devices/{device.id}",
        headers=auth_headers,
        json={"status": "retired"},
    )
    assert invalid_status.status_code == 422


def test_wave17_task_enums_reject_unknown_values(client, auth_headers, create_device) -> None:
    device = create_device(device_sn="wave17-task-device")

    invalid_update_task = client.post(
        "/api/update-tasks",
        headers=auth_headers,
        json={
            "name": "invalid execution",
            "task_type": "command",
            "command": "hostname",
            "target_filter": {"device_ids": [device.id]},
            "execution_mode": "danger",
        },
    )
    assert invalid_update_task.status_code == 422

    invalid_scheduled_task = client.post(
        "/api/scheduled-tasks",
        headers=auth_headers,
        json={
            "name": "invalid schedule type",
            "task_type": "cleanup",
            "schedule": "interval:60",
            "command": "hostname",
        },
    )
    assert invalid_scheduled_task.status_code == 422
