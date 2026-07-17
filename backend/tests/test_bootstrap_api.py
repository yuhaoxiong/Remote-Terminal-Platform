from io import BytesIO
import base64
import json
import os
from pathlib import Path
import shlex
import subprocess
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
    ssh_user: str = "edge",
) -> dict:
    response = client.post(
        "/api/devices",
        headers=headers,
        json={
            "name": "初始化设备",
            "device_sn": device_sn,
            "expected_profile_id": expected_profile_id,
            "ssh_user": ssh_user,
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
        assert "openssh-server sudo curl" in installer
        assert "/etc/sudoers.d/edge-platform-deploy" in installer
        assert "/usr/local/bin/edge-deploy apply --stdin" in installer
        assert "visudo -cf" in installer
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


def test_bootstrap_rejects_ssh_username_that_could_inject_sudoers(
    bootstrap_client: TestClient,
    bootstrap_headers: dict[str, str],
) -> None:
    device = _create_device(
        bootstrap_client,
        bootstrap_headers,
        device_sn="BOOTSTRAP-UNSAFE-USER",
        ssh_user="edge\nroot ALL=(ALL) NOPASSWD: ALL",
    )

    package = bootstrap_client.post(
        f"/api/devices/{device['id']}/bootstrap-package",
        headers=bootstrap_headers,
    )

    assert package.status_code == 200
    assert package.json()["status"] == "draft"
    assert any("SSH 用户名" in error for error in package.json()["validation_errors"])


def _download_edge_deploy_script(
    bootstrap_client: TestClient,
    bootstrap_headers: dict[str, str],
    *,
    device_sn: str,
) -> str:
    profile = bootstrap_client.get("/api/hardware-profiles", headers=bootstrap_headers).json()["items"][0]
    device = _create_device(
        bootstrap_client,
        bootstrap_headers,
        expected_profile_id=profile["id"],
        device_sn=device_sn,
    )
    package = bootstrap_client.post(
        f"/api/devices/{device['id']}/bootstrap-package",
        headers=bootstrap_headers,
    ).json()
    downloaded = bootstrap_client.get(
        f"/api/devices/{device['id']}/bootstrap-package/{package['id']}/download",
        headers=bootstrap_headers,
    )
    with ZipFile(BytesIO(downloaded.content)) as archive:
        return archive.read("bin/edge-deploy").decode("utf-8")


def test_ready_package_edge_deploy_cli_supports_safe_idempotent_function_apply(
    bootstrap_client: TestClient,
    bootstrap_headers: dict[str, str],
) -> None:
    script = _download_edge_deploy_script(
        bootstrap_client,
        bootstrap_headers,
        device_sn="BOOTSTRAP-EDGE-DEPLOY",
    )

    syntax = subprocess.run(
        ["bash", "-n"],
        input=script.encode("utf-8"),
        capture_output=True,
        check=False,
    )

    assert syntax.returncode == 0, syntax.stderr.decode("utf-8", errors="replace")
    assert "apply)" in script
    assert "--proto '=https'" in script
    assert "https://192.0.2.10/api/deployment-executions/" in script
    assert "artifact URL does not match platform execution" in script
    assert '[[ "$ca_cert_path" == /usr/local/share/ca-certificates/edge-platform-ca.crt ]]' in script
    assert "Authorization: Bearer" in script
    assert "--config" in script
    assert '-H "Authorization: Bearer $artifact_token"' not in script
    assert "sha256sum --check" in script
    assert "tarfile" in script
    assert 'steps=(preflight install configure start healthcheck)' in script
    assert "rollback_on_failure" in script
    assert "/var/lib/edge-platform/deployments" in script


def test_edge_deploy_cli_runtime_is_idempotent_when_root_is_available(
    bootstrap_client: TestClient,
    bootstrap_headers: dict[str, str],
) -> None:
    script = _download_edge_deploy_script(
        bootstrap_client,
        bootstrap_headers,
        device_sn="BOOTSTRAP-EDGE-RUNTIME",
    )

    runtime_script = EDGE_DEPLOY_RUNTIME_TEST.replace("\r\n", "\n").replace("\r", "\n").replace(
        "__EDGE_DEPLOY_SCRIPT__",
        base64.b64encode(script.encode("utf-8")).decode("ascii"),
    )
    runtime_command = ["wsl", "-u", "root", "-e", "bash"] if os.name == "nt" else ["bash"]
    runtime = subprocess.run(
        runtime_command,
        input=runtime_script.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    if b"EDGE_DEPLOY_RUNTIME_SKIP" in runtime.stdout:
        pytest.skip("当前环境没有 root 或免密 sudo，跳过 edge-deploy 运行级测试")
    assert runtime.returncode == 0, runtime.stderr.decode("utf-8", errors="replace")
    output_lines = runtime.stdout.decode("utf-8").splitlines()
    first_result = json.loads(output_lines[-3])
    second_result = json.loads(output_lines[-2])
    assert first_result["status"] == "succeeded"
    assert second_result == first_result
    assert output_lines[-1] == "5"


EDGE_DEPLOY_RUNTIME_TEST = r'''
set -euo pipefail
tmp="$(mktemp -d)"
if [[ "$(id -u)" -eq 0 ]]; then
  runner=(env)
  cleanup=(rm -rf "$tmp")
elif command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
  runner=(sudo -n env)
  cleanup=(sudo -n rm -rf "$tmp")
else
  printf '%s\n' EDGE_DEPLOY_RUNTIME_SKIP
  exit 0
fi
trap '"${cleanup[@]}"' EXIT
printf '%s' '__EDGE_DEPLOY_SCRIPT__' | base64 --decode >"$tmp/edge-deploy"
sed -i "s|/usr/local/share/ca-certificates/edge-platform-ca.crt|$tmp/ca.crt|g" "$tmp/edge-deploy"
chmod 0755 "$tmp/edge-deploy"
mkdir -p "$tmp/bin" "$tmp/package/demo-1.0.0-test/scripts" "$tmp/package/demo-1.0.0-test/artifacts"
cat >"$tmp/bin/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
output=""
while [[ $# -gt 0 ]]; do
  if [[ "$1" == --output ]]; then output="$2"; shift 2; else shift; fi
done
cp "$EDGE_TEST_ARTIFACT" "$output"
SH
chmod 0755 "$tmp/bin/curl"
for step in preflight install configure start; do
  cat >"$tmp/package/demo-1.0.0-test/scripts/$step.sh" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$(basename "$0" .sh)" >>"$EDGE_TEST_LOG"
printf '%s\n' '{"schema_version":1,"status":"succeeded","changed":true,"message":"ok"}'
SH
  chmod 0755 "$tmp/package/demo-1.0.0-test/scripts/$step.sh"
done
cat >"$tmp/package/demo-1.0.0-test/scripts/healthcheck.sh" <<'SH'
#!/usr/bin/env bash
printf '%s\n' healthcheck >>"$EDGE_TEST_LOG"
printf '%s\n' '{"schema_version":1,"status":"healthy","severity":"info","checked_at":"2026-07-17T00:00:00Z","checks":[{"name":"runtime","status":"passed"}]}'
SH
cat >"$tmp/package/demo-1.0.0-test/scripts/rollback.sh" <<'SH'
#!/usr/bin/env bash
printf '%s\n' '{"schema_version":1,"status":"succeeded","changed":true,"message":"rolled back"}'
SH
chmod 0755 "$tmp/package/demo-1.0.0-test/scripts/healthcheck.sh" "$tmp/package/demo-1.0.0-test/scripts/rollback.sh"
tar -czf "$tmp/artifact.tar.gz" -C "$tmp/package" demo-1.0.0-test
sha="$(sha256sum "$tmp/artifact.tar.gz" | awk '{print $1}')"
fingerprint="$(printf 'f%.0s' {1..64})"
printf test-ca >"$tmp/ca.crt"
make_descriptor() {
  jq -nc --arg token "$1" --arg sha "$sha" --arg fingerprint "$fingerprint" --arg ca "$tmp/ca.crt" --arg url "${2:-https://192.0.2.10/api/deployment-executions/11111111-1111-1111-1111-111111111111/items/1/artifact}" \
    '{schema_version:1,execution_id:"11111111-1111-1111-1111-111111111111",execution_item_id:1,function_code:"demo",version:"1.0.0",artifact_url:$url,artifact_token:$token,artifact_sha256:$sha,deployment_fingerprint:$fingerprint,config:{camera:0},rollback_on_failure:true,ca_cert_path:$ca}' | base64 -w0
}
run_apply() {
  "${runner[@]}" PATH="$tmp/bin:$PATH" EDGE_TEST_ARTIFACT="$tmp/artifact.tar.gz" EDGE_TEST_LOG="$tmp/lifecycle.log" \
    EDGE_DEPLOY_STATE_ROOT="$tmp/state" EDGE_DEPLOY_CACHE_ROOT="$tmp/cache" \
    "$tmp/edge-deploy" apply --stdin <<<"$1"
}
if run_apply "$(make_descriptor 'token-cccccccccccccccccccccccc' 'https://attacker.example/artifact')" >/dev/null 2>&1; then
  echo "untrusted artifact URL was accepted" >&2
  exit 1
fi
first="$(run_apply "$(make_descriptor 'token-aaaaaaaaaaaaaaaaaaaaaaaa')")"
second="$(run_apply "$(make_descriptor 'token-bbbbbbbbbbbbbbbbbbbbbbbb')")"
printf '%s\n%s\n%s\n' "$(jq -c . <<<"$first")" "$(jq -c . <<<"$second")" "$(wc -l <"$tmp/lifecycle.log" | tr -d ' ')"
'''


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
