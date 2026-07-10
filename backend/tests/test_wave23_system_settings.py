from cryptography.fernet import Fernet

from app.config import Settings
from app.database import init_db, session_scope
from app.main import create_app
from app.models.log import OperationLog
from app.models.system_setting import SystemSetting, SystemSettingChange


def _auth(client, username: str = "admin", password: str = "admin-pass") -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_operator(client, headers) -> dict[str, str]:
    created = client.post(
        "/api/users",
        headers=headers,
        json={"username": "operator", "password": "operator-pass", "role": "operator", "is_active": True},
    )
    assert created.status_code == 201
    return _auth(client, "operator", "operator-pass")


def test_system_settings_are_admin_only_and_reject_unknown_keys(client, auth_headers) -> None:
    operator_headers = _create_operator(client, auth_headers)

    forbidden = client.get("/api/system-settings/effective", headers=operator_headers)
    assert forbidden.status_code == 403

    unknown = client.put(
        "/api/system-settings/groups/remote_connection",
        headers=auth_headers,
        json={"values": {"UNKNOWN_KEY": "value"}},
    )
    assert unknown.status_code == 422
    assert "不支持的系统设置" in unknown.json()["detail"]


def test_system_setting_database_override_refreshes_effective_settings(client, auth_headers) -> None:
    saved = client.put(
        "/api/system-settings/groups/remote_connection",
        headers=auth_headers,
        json={"values": {"REMOTE_GATEWAY_HOST": "10.0.0.8", "SSH_TIMEOUT_SECONDS": 22}},
    )
    assert saved.status_code == 200
    assert saved.json()["requires_restart"] is False
    assert client.app.state.settings.remote_gateway_host == "10.0.0.8"
    assert client.app.state.settings.ssh_timeout_seconds == 22

    effective = client.get("/api/system-settings/effective", headers=auth_headers).json()
    values = {item["key"]: item for item in effective["items"]}
    assert values["REMOTE_GATEWAY_HOST"]["value"] == "10.0.0.8"
    assert values["REMOTE_GATEWAY_HOST"]["source"] == "database"

    reset = client.post("/api/system-settings/REMOTE_GATEWAY_HOST/reset", headers=auth_headers)
    assert reset.status_code == 200
    assert client.app.state.settings.remote_gateway_host == "127.0.0.1"


def test_sensitive_system_setting_requires_encryption_and_is_masked(client, auth_headers, initialized_settings) -> None:
    blocked = client.put(
        "/api/system-settings/groups/device_credentials",
        headers=auth_headers,
        json={"values": {"DEFAULT_DEVICE_SSH_PASSWORD": "new-secret"}},
    )
    assert blocked.status_code == 422
    assert "未配置 CREDENTIAL_ENCRYPTION_KEY" in blocked.json()["detail"]

    encrypted_settings = initialized_settings.model_copy(
        update={"credential_encryption_key": Fernet.generate_key().decode("utf-8")}
    )
    init_db(encrypted_settings)
    encrypted_client = create_app(encrypted_settings)

    from fastapi.testclient import TestClient

    with TestClient(encrypted_client) as local_client:
        headers = _auth(local_client)
        saved = local_client.put(
            "/api/system-settings/groups/remote_connection",
            headers=headers,
            json={"values": {"DEFAULT_VNC_PASSWORD": "new-secret"}},
        )
        assert saved.status_code == 200
        serialized = str(saved.json())
        assert "new-secret" not in serialized
        assert local_client.app.state.settings.default_vnc_password == "new-secret"

        with session_scope(encrypted_settings) as session:
            setting = session.query(SystemSetting).filter(SystemSetting.key == "DEFAULT_VNC_PASSWORD").one()
            assert setting.secret_value_encrypted != "new-secret"
            change = session.query(SystemSettingChange).filter(SystemSettingChange.setting_key == "DEFAULT_VNC_PASSWORD").one()
            assert change.new_value_snapshot == "***"


def test_restart_required_settings_persist_pending_state_and_write_logs(client, auth_headers, initialized_settings) -> None:
    saved = client.put(
        "/api/system-settings/groups/file_storage",
        headers=auth_headers,
        json={"values": {"FILE_BACKEND": "local", "FILE_STORAGE_DIR": "C:/edge-files"}},
    )
    assert saved.status_code == 200
    assert saved.json()["requires_restart"] is True
    assert saved.json()["pending_restart_count"] >= 1

    with session_scope(initialized_settings) as session:
        assert session.query(SystemSetting).filter(SystemSetting.pending_restart.is_(True)).count() >= 1
        assert session.query(SystemSettingChange).filter(SystemSettingChange.action == "save").count() >= 1
        assert session.query(OperationLog).filter(OperationLog.action == "system_settings.save").count() >= 1


def test_file_backend_setting_supports_sftp(client, auth_headers) -> None:
    schema = client.get("/api/system-settings/schema", headers=auth_headers)

    assert schema.status_code == 200
    file_backend = next(item for item in schema.json()["items"] if item["key"] == "FILE_BACKEND")
    assert file_backend["options"] == ["local", "sftp"]

    saved = client.put(
        "/api/system-settings/groups/file_storage",
        headers=auth_headers,
        json={"values": {"FILE_BACKEND": "sftp"}},
    )
    assert saved.status_code == 200
    assert saved.json()["requires_restart"] is True


def test_restart_endpoint_requires_systemd(client, auth_headers) -> None:
    response = client.post("/api/system-settings/restart", headers=auth_headers, json={"confirm_text": "确认重启"})

    assert response.status_code == 409
    assert "systemd" in response.json()["detail"]


def test_diagnostics_includes_system_settings_summary(client, auth_headers) -> None:
    response = client.get("/api/diagnostics/config", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["system_settings"]["database_override_count"] == 0
    assert body["system_settings"]["pending_restart_count"] == 0
    assert body["system_settings"]["credential_encryption_configured"] is False
