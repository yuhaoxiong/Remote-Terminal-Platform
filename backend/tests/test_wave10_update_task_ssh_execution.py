from app.services.ssh_service import RemoteAuthenticationError


def _auth(client) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_device(client, headers: dict[str, str], device_sn: str, *, project_id: int | None = None) -> int:
    response = client.post(
        "/api/devices",
        headers=headers,
        json={
            "name": f"Device {device_sn}",
            "device_sn": device_sn,
            "project_id": project_id,
            "ssh_user": "ztl",
            "ssh_password": "123456",
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


class FakeSshService:
    def __init__(self, results: list[tuple[int, str, str] | Exception]) -> None:
        self.results = list(results)
        self.calls: list[tuple[int, str]] = []

    def execute(self, device, command: str, timeout: int | None = None):
        self.calls.append((device.id, command))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _create_task(client, headers: dict[str, str], payload: dict) -> dict:
    response = client.post("/api/update-tasks", headers=headers, json=payload)
    assert response.status_code == 201
    return response.json()


def test_dry_run_update_task_does_not_call_ssh(client, create_project) -> None:
    headers = _auth(client)
    project = create_project("wave10")
    _create_device(client, headers, "dry-001", project_id=project.id)
    fake_ssh = FakeSshService(results=[])
    client.app.state.ssh_service = fake_ssh

    task = _create_task(
        client,
        headers,
        {
            "name": "演练任务",
            "task_type": "command",
            "command": "hostname",
            "target_filter": {"project_id": project.id},
        },
    )
    executed = client.post(f"/api/update-tasks/{task['id']}/execute", headers=headers)

    assert executed.status_code == 200
    body = executed.json()
    assert body["execution_mode"] == "dry_run"
    assert body["status"] == "completed"
    assert body["devices"][0]["status"] == "skipped"
    assert "演练模式" in body["devices"][0]["output_summary"]
    assert fake_ssh.calls == []


def test_ssh_command_records_success_output(client) -> None:
    headers = _auth(client)
    device_id = _create_device(client, headers, "success-001")
    fake_ssh = FakeSshService(results=[(0, "edge-host\n", "")])
    client.app.state.ssh_service = fake_ssh

    task = _create_task(
        client,
        headers,
        {
            "name": "真实命令",
            "task_type": "command",
            "command": "hostname",
            "target_filter": {"device_ids": [device_id]},
            "execution_mode": "ssh_command",
            "failure_strategy": "continue",
        },
    )
    executed = client.post(f"/api/update-tasks/{task['id']}/execute", headers=headers)

    assert executed.status_code == 200
    row = executed.json()["devices"][0]
    assert executed.json()["status"] == "completed"
    assert row["status"] == "success"
    assert row["exit_code"] == 0
    assert row["stdout_summary"] == "edge-host\n"
    assert fake_ssh.calls == [(device_id, "hostname")]


def test_ssh_command_records_non_zero_exit(client) -> None:
    headers = _auth(client)
    device_id = _create_device(client, headers, "fail-001")
    client.app.state.ssh_service = FakeSshService(results=[(2, "", "not ok")])

    task = _create_task(
        client,
        headers,
        {
            "name": "失败命令",
            "task_type": "command",
            "command": "hostname",
            "target_filter": {"device_ids": [device_id]},
            "execution_mode": "ssh_command",
            "failure_strategy": "continue",
        },
    )
    executed = client.post(f"/api/update-tasks/{task['id']}/execute", headers=headers)

    row = executed.json()["devices"][0]
    assert executed.json()["status"] == "partial_failed"
    assert row["status"] == "failed"
    assert row["exit_code"] == 2
    assert row["stderr_summary"] == "not ok"
    assert "退出码" in row["error_message"]


def test_ssh_command_auth_failure_is_redacted(client) -> None:
    headers = _auth(client)
    device_id = _create_device(client, headers, "auth-001")
    client.app.state.ssh_service = FakeSshService(results=[RemoteAuthenticationError("password 123456 leaked")])

    task = _create_task(
        client,
        headers,
        {
            "name": "认证失败",
            "task_type": "command",
            "command": "hostname",
            "target_filter": {"device_ids": [device_id]},
            "execution_mode": "ssh_command",
        },
    )
    executed = client.post(f"/api/update-tasks/{task['id']}/execute", headers=headers)

    row = executed.json()["devices"][0]
    assert row["status"] == "failed"
    assert row["error_message"] == "SSH 认证失败"
    assert "123456" not in row["error_message"]


def test_pause_strategy_skips_devices_after_first_failure(client, create_project) -> None:
    headers = _auth(client)
    project = create_project("pause")
    first_id = _create_device(client, headers, "pause-001", project_id=project.id)
    second_id = _create_device(client, headers, "pause-002", project_id=project.id)
    fake_ssh = FakeSshService(results=[(1, "", "failed")])
    client.app.state.ssh_service = fake_ssh

    task = _create_task(
        client,
        headers,
        {
            "name": "暂停策略",
            "task_type": "command",
            "command": "hostname",
            "target_filter": {"project_id": project.id},
            "execution_mode": "ssh_command",
            "failure_strategy": "pause",
        },
    )
    executed = client.post(f"/api/update-tasks/{task['id']}/execute", headers=headers)

    rows = executed.json()["devices"]
    assert executed.json()["status"] == "partial_failed"
    assert [row["device_id"] for row in rows] == [first_id, second_id]
    assert rows[0]["status"] == "failed"
    assert rows[1]["status"] == "skipped"
    assert fake_ssh.calls == [(first_id, "hostname")]
