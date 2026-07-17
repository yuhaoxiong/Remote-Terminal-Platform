from io import BytesIO
from pathlib import Path
import shlex
from zipfile import ZipFile

from cryptography.fernet import Fernet
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import session_scope
from app.main import create_app
from app.models.bootstrap import DeviceBootstrapPackage
from app.models.device import Device


@pytest.fixture()
def bootstrap_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'bootstrap.db'}",
        jwt_secret_key="bootstrap-test-secret",
        default_admin_username="admin",
        default_admin_password="admin-pass",
        scheduler_enabled=False,
        credential_encryption_key=Fernet.generate_key().decode("ascii"),
        bootstrap_platform_url="https://192.0.2.10",
        bootstrap_ca_certificate="-----BEGIN CERTIFICATE-----\nTEST-CA\n-----END CERTIFICATE-----\n",
        bootstrap_frp_server_addr="192.0.2.10",
        bootstrap_frp_server_port=7000,
        bootstrap_frp_auth_token="frp-test-token",
        bootstrap_frpc_download_url="https://downloads.example.test/frp.tar.gz",
        bootstrap_frpc_sha256="a" * 64,
    )


@pytest.fixture()
def bootstrap_client(bootstrap_settings: Settings):
    with TestClient(create_app(bootstrap_settings)) as client:
        yield client


@pytest.fixture()
def bootstrap_headers(bootstrap_client: TestClient) -> dict[str, str]:
    response = bootstrap_client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_device(
    client: TestClient,
    headers: dict[str, str],
    *,
    expected_profile_id: int | None = None,
    device_sn: str = "BOOTSTRAP-001",
) -> dict:
    response = client.post(
        "/api/devices",
        headers=headers,
        json={
            "name": "初始化设备",
            "device_sn": device_sn,
            "expected_profile_id": expected_profile_id,
            "ssh_user": "edge",
            "ssh_password": "device-pass",
        },
    )
    assert response.status_code == 201
    return response.json()


def _secret_from_env(archive: ZipFile, key: str) -> str:
    env = archive.read("config/device.env").decode("utf-8")
    raw_value = next(line.split("=", 1)[1] for line in env.splitlines() if line.startswith(f"{key}="))
    return shlex.split(raw_value)[0]


def test_device_creation_makes_draft_and_reports_missing_platform_configuration(client, auth_headers) -> None:
    device = _create_device(client, auth_headers)
    draft = client.get(f"/api/devices/{device['id']}/bootstrap-package", headers=auth_headers)
    assert draft.status_code == 200
    assert draft.json()["status"] == "draft"
    assert draft.json()["generation"] == 1

    prepared = client.post(f"/api/devices/{device['id']}/bootstrap-package", headers=auth_headers)
    assert prepared.status_code == 200
    assert prepared.json()["status"] == "draft"
    assert any("CREDENTIAL_ENCRYPTION_KEY" in item for item in prepared.json()["validation_errors"])
    assert "token" not in prepared.text.lower()


def test_ready_package_contains_device_specific_installer_and_uses_one_time_claim(
    bootstrap_client: TestClient,
    bootstrap_headers: dict[str, str],
    bootstrap_settings: Settings,
) -> None:
    profiles = bootstrap_client.get("/api/hardware-profiles", headers=bootstrap_headers).json()["items"]
    profile = next(item for item in profiles if item["code"] == "rk3588-8g-debian11")
    device = _create_device(bootstrap_client, bootstrap_headers, expected_profile_id=profile["id"])

    prepared = bootstrap_client.post(
        f"/api/devices/{device['id']}/bootstrap-package",
        headers=bootstrap_headers,
    )
    assert prepared.status_code == 200
    package = prepared.json()
    assert package["status"] == "ready"
    assert package["validation_errors"] is None
    assert "token" not in prepared.text.lower()

    downloaded = bootstrap_client.get(
        f"/api/devices/{device['id']}/bootstrap-package/{package['id']}/download",
        headers=bootstrap_headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(downloaded.content)) as archive:
        assert {
            "install.sh",
            "config/device.env",
            "config/frpc.toml",
            "config/platform-ca.crt",
            "bin/edge-deploy",
            "scripts/hardware_collect.sh",
            "scripts/register.sh",
            "systemd/frpc.service",
            "systemd/x0vncserver.service",
            "systemd/edge-governor.service",
        }.issubset(archive.namelist())
        token = _secret_from_env(archive, "REGISTRATION_TOKEN")
        vnc_password = _secret_from_env(archive, "VNC_PASSWORD")
        installer = archive.read("install.sh").decode("utf-8")
        assert "apt-get update" in installer
        assert "dist-upgrade" not in installer
        assert "\nreboot\n" not in installer
        assert "shutdown -r" not in installer
        assert "chmod 0600" in installer
        assert "x0vncserver" in archive.read("systemd/x0vncserver.service").decode("utf-8")
        assert "remotePort = 10000" in archive.read("config/frpc.toml").decode("utf-8")
        assert "remotePort = 10500" in archive.read("config/frpc.toml").decode("utf-8")

    with session_scope(bootstrap_settings) as session:
        stored = session.get(DeviceBootstrapPackage, package["id"])
        assert stored is not None
        assert stored.token_encrypted != token
        assert stored.vnc_password_encrypted

    failed_claim = bootstrap_client.post(
        "/api/device-registration/claim",
        json={
            "token": token,
            "device_uuid": device["device_uuid"],
            "device_sn": device["device_sn"],
            "machine_id": "machine-one",
            "mac_addresses": ["02:00:00:00:00:02", "02:00:00:00:00:01"],
            "hardware": {"soc": "rk3588", "memory_mb": 7800, "os_version": "debian11"},
            "ssh_ready": False,
            "vnc_ready": False,
            "bootstrap_status": "failed",
            "error_message": "ssh unavailable",
        },
    )
    assert failed_claim.status_code == 200
    assert failed_claim.json()["accepted"] is False

    successful_claim = bootstrap_client.post(
        "/api/device-registration/claim",
        json={
            "token": token,
            "device_uuid": device["device_uuid"],
            "device_sn": device["device_sn"],
            "machine_id": "machine-one",
            "mac_addresses": ["02:00:00:00:00:01"],
            "hardware": {"soc": "rockchip,rk3588", "memory_mb": 7800, "os_version": "debian11"},
            "ssh_ready": True,
            "vnc_ready": False,
            "bootstrap_status": "ready",
        },
    )
    assert successful_claim.status_code == 200
    assert successful_claim.json() == {
        "device_id": device["id"],
        "accepted": True,
        "status": "ready_vnc_pending",
        "vnc_status": "pending",
        "hardware_profile_id": profile["id"],
        "hardware_matches_expected": True,
    }

    reused = bootstrap_client.post(
        "/api/device-registration/claim",
        json={
            "token": token,
            "device_uuid": device["device_uuid"],
            "device_sn": device["device_sn"],
            "hardware": {"soc": "rk3588", "memory_mb": 7800, "os_version": "debian11"},
            "ssh_ready": True,
            "vnc_ready": True,
            "bootstrap_status": "ready",
        },
    )
    assert reused.status_code == 409

    detail = bootstrap_client.get(f"/api/devices/{device['id']}", headers=bootstrap_headers).json()
    assert detail["initialization_status"] == "ready_vnc_pending"
    assert detail["actual_profile_id"] == profile["id"]
    assert detail["initialized_at"]
    remote_vnc = bootstrap_client.post(
        f"/api/devices/{device['id']}/remote/vnc",
        headers=bootstrap_headers,
    )
    assert remote_vnc.status_code == 200
    assert remote_vnc.json()["vnc_password"] == vnc_password


def test_connection_change_invalidates_ready_package(
    bootstrap_client: TestClient,
    bootstrap_headers: dict[str, str],
) -> None:
    device = _create_device(bootstrap_client, bootstrap_headers)
    package = bootstrap_client.post(
        f"/api/devices/{device['id']}/bootstrap-package",
        headers=bootstrap_headers,
    ).json()
    assert package["status"] == "ready"

    updated = bootstrap_client.put(
        f"/api/devices/{device['id']}",
        headers=bootstrap_headers,
        json={"ssh_port": 10020},
    )
    assert updated.status_code == 200
    assert updated.json()["initialization_status"] == "package_stale"
    latest = bootstrap_client.get(
        f"/api/devices/{device['id']}/bootstrap-package",
        headers=bootstrap_headers,
    ).json()
    assert latest["status"] == "draft"
    assert latest["generation"] == package["generation"] + 1

    stale_download = bootstrap_client.get(
        f"/api/devices/{device['id']}/bootstrap-package/{package['id']}/download",
        headers=bootstrap_headers,
    )
    assert stale_download.status_code == 409


def test_registration_records_hardware_mismatch_without_blocking_management_baseline(
    bootstrap_client: TestClient,
    bootstrap_headers: dict[str, str],
) -> None:
    profiles = bootstrap_client.get("/api/hardware-profiles", headers=bootstrap_headers).json()["items"]
    expected = next(item for item in profiles if item["code"] == "rk3588-8g-debian11")
    actual = next(item for item in profiles if item["code"] == "rk3568-4g-debian11")
    device = _create_device(
        bootstrap_client,
        bootstrap_headers,
        expected_profile_id=expected["id"],
        device_sn="BOOTSTRAP-MISMATCH",
    )
    package = bootstrap_client.post(
        f"/api/devices/{device['id']}/bootstrap-package",
        headers=bootstrap_headers,
    ).json()
    archive_response = bootstrap_client.get(
        f"/api/devices/{device['id']}/bootstrap-package/{package['id']}/download",
        headers=bootstrap_headers,
    )
    with ZipFile(BytesIO(archive_response.content)) as archive:
        token = _secret_from_env(archive, "REGISTRATION_TOKEN")

    claimed = bootstrap_client.post(
        "/api/device-registration/claim",
        json={
            "token": token,
            "device_uuid": device["device_uuid"],
            "device_sn": device["device_sn"],
            "hardware": {"soc": "rk3568", "memory_mb": 3900, "os_version": "debian11"},
            "ssh_ready": True,
            "vnc_ready": True,
            "bootstrap_status": "ready",
        },
    )
    assert claimed.status_code == 200
    assert claimed.json()["accepted"] is True
    assert claimed.json()["status"] == "hardware_mismatch"
    assert claimed.json()["hardware_profile_id"] == actual["id"]
    assert claimed.json()["hardware_matches_expected"] is False


def test_bootstrap_package_mutations_require_admin(client, auth_headers) -> None:
    device = _create_device(client, auth_headers)
    created = client.post(
        "/api/users",
        headers=auth_headers,
        json={"username": "bootstrap-operator", "password": "operator-pass", "role": "operator"},
    )
    assert created.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"username": "bootstrap-operator", "password": "operator-pass"},
    )
    operator_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get(
        f"/api/devices/{device['id']}/bootstrap-package",
        headers=operator_headers,
    ).status_code == 200
    assert client.post(
        f"/api/devices/{device['id']}/bootstrap-package",
        headers=operator_headers,
    ).status_code == 403
