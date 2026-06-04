from app.database import session_scope
from app.models.log import OperationLog
from app.models.user import User


def _login(client, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_operator(client, auth_headers, *, username: str = "operator", password: str = "operator-pass") -> tuple[int, dict[str, str]]:
    response = client.post(
        "/api/users",
        headers=auth_headers,
        json={"username": username, "password": password, "role": "operator", "is_active": True},
    )
    assert response.status_code == 201
    return response.json()["id"], _login(client, username, password)


def test_admin_manages_users_and_operator_is_forbidden(client, auth_headers) -> None:
    operator_id, operator_headers = _create_operator(client, auth_headers)

    me = client.get("/api/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["role"] == "admin"

    users = client.get("/api/users", headers=auth_headers)
    assert users.status_code == 200
    assert users.json()["total"] == 2

    forbidden = client.get("/api/users", headers=operator_headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "当前账号无权限执行该操作"

    updated = client.put(f"/api/users/{operator_id}", headers=auth_headers, json={"role": "operator", "is_active": True})
    assert updated.status_code == 200
    assert updated.json()["role"] == "operator"

    reset = client.post(
        f"/api/users/{operator_id}/reset-password",
        headers=auth_headers,
        json={"new_password": "operator-new-pass"},
    )
    assert reset.status_code == 200
    assert "password_hash" not in reset.text

    disabled = client.post(f"/api/users/{operator_id}/toggle", headers=auth_headers, json={"is_active": False})
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False

    assert client.post("/api/auth/login", json={"username": "operator", "password": "operator-new-pass"}).status_code == 401


def test_cannot_disable_last_active_admin(client, auth_headers) -> None:
    me = client.get("/api/auth/me", headers=auth_headers).json()
    response = client.post(f"/api/users/{me['id']}/toggle", headers=auth_headers, json={"is_active": False})
    assert response.status_code == 409
    assert "最后一个启用的管理员" in response.json()["detail"]


def test_disabled_user_refresh_fails(client, auth_headers) -> None:
    operator_id, _operator_headers = _create_operator(client, auth_headers, username="refresh-operator", password="operator-pass")
    login = client.post("/api/auth/login", json={"username": "refresh-operator", "password": "operator-pass"})
    refresh_token = login.json()["refresh_token"]

    client.post(f"/api/users/{operator_id}/toggle", headers=auth_headers, json={"is_active": False})
    refresh = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh.status_code == 401


def test_operator_permission_matrix(client, auth_headers, create_device, create_update_task, initialized_settings) -> None:
    _operator_id, operator_headers = _create_operator(client, auth_headers, username="matrix-operator", password="operator-pass")
    device = create_device(device_sn="MATRIX-001")

    create_response = client.post(
        "/api/devices",
        headers=operator_headers,
        json={"name": "operator device", "device_sn": "OP-001", "project_id": "operator-project"},
    )
    assert create_response.status_code == 201

    delete_response = client.delete(f"/api/devices/{device.id}", headers=operator_headers)
    assert delete_response.status_code == 403

    dry_run = client.post(
        "/api/update-tasks",
        headers=operator_headers,
        json={
            "name": "operator dry-run",
            "task_type": "command",
            "command": "hostname",
            "execution_mode": "dry_run",
            "failure_strategy": "continue",
            "concurrency_limit": 1,
            "target_filter": {"device_ids": [device.id]},
        },
    )
    assert dry_run.status_code == 201

    ssh_task = client.post(
        "/api/update-tasks",
        headers=operator_headers,
        json={
            "name": "operator ssh",
            "task_type": "command",
            "command": "hostname",
            "execution_mode": "ssh_command",
            "failure_strategy": "continue",
            "concurrency_limit": 1,
            "target_filter": {"device_ids": [device.id]},
        },
    )
    assert ssh_task.status_code == 403

    scheduled = client.post(
        "/api/scheduled-tasks",
        headers=operator_headers,
        json={"name": "operator scheduled", "task_type": "command", "schedule": "interval:60", "command": "hostname"},
    )
    assert scheduled.status_code == 403

    with session_scope(initialized_settings) as session:
        assert session.query(OperationLog).filter(OperationLog.action == "auth.forbidden", OperationLog.user_id.isnot(None)).count() >= 1


def test_auth_events_are_logged(client, auth_headers, initialized_settings) -> None:
    client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass"})

    with session_scope(initialized_settings) as session:
        logs = list(session.query(OperationLog).filter(OperationLog.action == "auth.login").all())
        assert {log.status for log in logs} >= {"success", "failed"}
        assert all("admin-pass" not in (log.detail or "") for log in logs)

        admin = session.query(User).filter(User.username == "admin").one()
        assert admin.role == "admin"
        assert admin.last_login_at is not None
