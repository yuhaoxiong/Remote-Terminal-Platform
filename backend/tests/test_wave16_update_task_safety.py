from app.database import session_scope
from app.models.device import Device
from app.services.ssh_service import RemoteConnectionError


def _auth(client) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_group(client, headers: dict[str, str], name: str = "Wave16 分组") -> int:
    response = client.post("/api/groups", headers=headers, json={"name": name})
    assert response.status_code == 201
    return int(response.json()["id"])


def _create_device(
    client,
    headers: dict[str, str],
    device_sn: str,
    *,
    project_id: str = "wave16",
    group_id: int | None = None,
    tags: list[str] | None = None,
    ssh_password: str | None = "123456",
) -> int:
    payload = {
        "name": f"Device {device_sn}",
        "device_sn": device_sn,
        "project_id": project_id,
        "group_id": group_id,
        "tags": tags or [],
        "ssh_user": "ztl",
    }
    if ssh_password is not None:
        payload["ssh_password"] = ssh_password
    response = client.post("/api/devices", headers=headers, json=payload)
    assert response.status_code == 201
    return int(response.json()["id"])


class FakeSshService:
    def __init__(self, results: list[tuple[int, str, str] | Exception]) -> None:
        self.results = list(results)

    def execute(self, device, command: str, timeout: int | None = None):
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_preview_targets_reuses_filters_and_redacts_credentials(client, initialized_settings) -> None:
    headers = _auth(client)
    group_id = _create_group(client, headers)
    first_id = _create_device(client, headers, "preview-001", group_id=group_id, tags=["vision", "prod"])
    _create_device(client, headers, "preview-002", project_id="other", group_id=group_id, tags=["vision"])
    missing_credential_id = _create_device(
        client,
        headers,
        "preview-003",
        group_id=group_id,
        tags=["vision", "prod"],
        ssh_password=None,
    )
    with session_scope(initialized_settings) as session:
        device = session.get(Device, missing_credential_id)
        assert device is not None
        device.ssh_password_encrypted = None
        device.ssh_key_encrypted = None

    preview = client.post(
        "/api/update-tasks/preview-targets",
        headers=headers,
        json={
            "execution_mode": "ssh_command",
            "target_filter": {"project_id": "wave16", "group_id": group_id, "tags": ["vision", "prod"]},
        },
    )

    assert preview.status_code == 200
    body = preview.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [first_id, missing_credential_id]
    assert any("缺少 SSH 凭据" in warning for warning in body["warnings"])
    assert "123456" not in preview.text

    created = client.post(
        "/api/update-tasks",
        headers=headers,
        json={
            "name": "预览一致性任务",
            "task_type": "command",
            "command": "hostname",
            "target_filter": {"project_id": "wave16", "group_id": group_id, "tags": ["vision", "prod"]},
        },
    )
    assert created.status_code == 201
    assert [row["device_id"] for row in created.json()["devices"]] == [first_id, missing_credential_id]


def test_update_task_template_crud_and_sensitive_field_rejection(client) -> None:
    headers = _auth(client)

    created = client.post(
        "/api/update-task-templates",
        headers=headers,
        json={
            "name": "查看主机名",
            "description": "只读取主机名",
            "command": "hostname",
            "task_type": "command",
            "default_execution_mode": "dry_run",
            "ssh_password": "should-not-be-accepted",
        },
    )
    assert created.status_code == 201
    template_id = created.json()["id"]
    assert "ssh_password" not in created.text

    listed = client.get("/api/update-task-templates", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    updated = client.put(
        f"/api/update-task-templates/{template_id}",
        headers=headers,
        json={"name": "查看当前用户", "command": "whoami", "default_execution_mode": "ssh_command"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "查看当前用户"
    assert updated.json()["command"] == "whoami"
    assert updated.json()["default_execution_mode"] == "ssh_command"

    deleted = client.delete(f"/api/update-task-templates/{template_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get("/api/update-task-templates", headers=headers).json()["total"] == 0


def test_update_task_result_export_csv_sanitizes_summaries(client) -> None:
    headers = _auth(client)
    first_id = _create_device(client, headers, "export-001")
    second_id = _create_device(client, headers, "export-002")
    client.app.state.ssh_service = FakeSshService(results=[(0, "+ok", ""), RemoteConnectionError("=connection failed")])

    created = client.post(
        "/api/update-tasks",
        headers=headers,
        json={
            "name": "导出任务",
            "task_type": "command",
            "command": "hostname",
            "target_filter": {"device_ids": [first_id, second_id]},
            "execution_mode": "ssh_command",
        },
    )
    assert created.status_code == 201
    executed = client.post(f"/api/update-tasks/{created.json()['id']}/execute", headers=headers)
    assert executed.status_code == 200
    assert executed.json()["status"] == "partial_failed"

    exported = client.get(f"/api/update-tasks/{created.json()['id']}/export", headers=headers)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert exported.headers["content-disposition"] == f'attachment; filename="update_task_{created.json()["id"]}_results.csv"'
    assert "stdout_summary" in exported.text
    assert "\t+ok" in exported.text
    assert "\t=connection failed" in exported.text
    assert "123456" not in exported.text
