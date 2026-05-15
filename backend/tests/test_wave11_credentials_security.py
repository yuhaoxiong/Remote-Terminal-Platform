import sys
from pathlib import Path
from types import SimpleNamespace

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import init_db, session_scope
from app.main import create_app
from app.models.device import Device
from app.services.encryption import EncryptionService
from app.services.ssh_service import SshService


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        jwt_secret_key="test-secret-key",
        default_admin_username="admin",
        default_admin_password="admin-pass",
        credential_encryption_key=Fernet.generate_key().decode("utf-8"),
    )


def _auth(client: TestClient, password: str = "admin-pass") -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "admin", "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_encryption_service_encrypts_and_keeps_legacy_plaintext_readable(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    service = EncryptionService(settings)

    encrypted = service.encrypt_optional("123456")

    assert encrypted is not None
    assert encrypted != "123456"
    assert service.decrypt_optional(encrypted) == "123456"
    assert service.decrypt_optional("legacy-pass") == "legacy-pass"
    assert service.encrypt_optional(None) is None


def test_device_create_update_and_frps_import_store_encrypted_passwords(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings)
    client = TestClient(create_app(settings))
    headers = _auth(client)

    created = client.post(
        "/api/devices",
        headers=headers,
        json={"name": "Edge", "device_sn": "enc-001", "project_id": "secure", "ssh_password": "secret-pass"},
    )
    assert created.status_code == 201
    assert "secret-pass" not in str(created.json())

    with session_scope(settings) as session:
        device = session.query(Device).filter(Device.device_sn == "enc-001").one()
        stored = device.ssh_password_encrypted
        assert stored is not None
        assert stored != "secret-pass"
        assert EncryptionService(settings).decrypt_optional(stored) == "secret-pass"

    updated = client.put(
        f"/api/devices/{created.json()['id']}",
        headers=headers,
        json={"name": "Edge updated", "ssh_password": "rotated-pass"},
    )
    assert updated.status_code == 200
    assert "rotated-pass" not in str(updated.json())

    with session_scope(settings) as session:
        device = session.query(Device).filter(Device.device_sn == "enc-001").one()
        assert EncryptionService(settings).decrypt_optional(device.ssh_password_encrypted) == "rotated-pass"

    class FakeFrpsClient:
        def fetch_tcp_proxies(self, payload):
            return [
                {"name": "ssh-12008", "conf": {"remotePort": 12008}, "status": "online"},
                {"name": "vnc-17008", "conf": {"remotePort": 17008}, "status": "online"},
            ]

    client.app.state.frps_dashboard_client = FakeFrpsClient()
    imported = client.post(
        "/api/frps/import",
        headers=headers,
        json={
            "dashboard_url": "127.0.0.1:7500",
            "username": "admin",
            "password": "admin",
            "ssh_port_start": 12001,
            "ssh_port_end": 17000,
            "vnc_port_start": 17001,
            "vnc_port_end": 22000,
            "project_id": "frps-secure",
        },
    )
    assert imported.status_code == 200

    with session_scope(settings) as session:
        device = session.query(Device).filter(Device.device_sn == "frps-12008").one()
        assert device.ssh_password_encrypted != "123456"
        assert EncryptionService(settings).decrypt_optional(device.ssh_password_encrypted) == "123456"


def test_ssh_service_uses_decrypted_device_password_and_accepts_legacy_plaintext(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    encrypted = EncryptionService(settings).encrypt_optional("secret-pass")
    captured: list[dict] = []

    class FakeAuthenticationException(Exception):
        pass

    class FakeSSHException(Exception):
        pass

    class FakeSSHClient:
        def load_system_host_keys(self) -> None:
            pass

        def set_missing_host_key_policy(self, policy) -> None:
            pass

        def connect(self, **kwargs) -> None:
            captured.append(kwargs)

        def close(self) -> None:
            pass

    fake_paramiko = SimpleNamespace(
        SSHClient=FakeSSHClient,
        AutoAddPolicy=lambda: object(),
        AuthenticationException=FakeAuthenticationException,
        SSHException=FakeSSHException,
    )
    monkeypatch.setitem(sys.modules, "paramiko", fake_paramiko)

    service = SshService(settings)
    service._connect(Device(id=1, name="one", device_sn="one", project_id="p", ssh_port=12001, ssh_user="ztl", ssh_password_encrypted=encrypted))
    service._connect(Device(id=2, name="two", device_sn="two", project_id="p", ssh_port=12002, ssh_user="ztl", ssh_password_encrypted="legacy-pass"))

    assert captured[0]["password"] == "secret-pass"
    assert captured[1]["password"] == "legacy-pass"


def test_diagnostics_security_summary_is_non_sensitive(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        jwt_secret_key="change-me-in-production",
        default_admin_username="admin",
        default_admin_password="admin",
        default_device_ssh_password="123456",
    )
    init_db(settings)
    client = TestClient(create_app(settings))
    headers = _auth(client, password="admin")

    response = client.get("/api/diagnostics/config", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["security"]["credential_encryption_configured"] is False
    assert body["security"]["jwt_secret_configured"] is False
    assert body["security"]["default_admin_password_in_use"] is True
    assert body["security"]["default_device_ssh_password_in_use"] is True
    assert body["security"]["warnings"]
    serialized = str(body)
    assert "change-me-in-production" not in serialized
    assert "123456" not in serialized
    assert "admin-pass" not in serialized
