from pathlib import Path

import pytest

from app.config import Settings
from app.services.file_service import FileService, RemoteFileNotFoundError
from app.services.ssh_service import RemoteConnectionError


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        jwt_secret_key="test-secret-key",
        default_admin_username="admin",
        default_admin_password="admin-pass",
        scheduler_enabled=False,
        file_backend="local",
    )


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-pass"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _device_payload(device_sn: str = "edge-files-001") -> dict[str, object]:
    return {
        "name": "File transfer edge",
        "device_sn": device_sn,
        "project_id": "factory-files",
        "ssh_user": "root",
        "tags": ["files"],
    }


def test_device_file_browser_upload_download_and_delete(client) -> None:
    headers = _auth_headers(client)
    created = client.post("/api/devices", headers=headers, json=_device_payload())
    assert created.status_code == 201
    device_id = created.json()["id"]

    empty_list = client.get(f"/api/devices/{device_id}/files?path=/opt/app", headers=headers)
    assert empty_list.status_code == 200
    assert empty_list.json() == {"device_id": device_id, "path": "/opt/app", "items": []}

    uploaded = client.post(
        f"/api/devices/{device_id}/files/upload",
        headers=headers,
        json={
            "remote_path": "/opt/app/config.yaml",
            "content": "mode: wave6\n",
        },
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["status"] == "uploaded"
    assert uploaded.json()["size"] == 12

    listed = client.get(f"/api/devices/{device_id}/files?path=/opt/app", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["name"] == "config.yaml"
    assert listed.json()["items"][0]["type"] == "file"

    downloaded = client.get(
        f"/api/devices/{device_id}/files/download?remote_path=/opt/app/config.yaml",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert "attachment" in downloaded.headers["content-disposition"]
    assert downloaded.text == "mode: wave6\n"

    deleted = client.request(
        "DELETE",
        f"/api/devices/{device_id}/files",
        headers=headers,
        json={"remote_path": "/opt/app/config.yaml"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"

    missing = client.get(
        f"/api/devices/{device_id}/files/download?remote_path=/opt/app/config.yaml",
        headers=headers,
    )
    assert missing.status_code == 404


def test_device_file_upload_and_download_binary_content(client) -> None:
    headers = _auth_headers(client)
    created = client.post("/api/devices", headers=headers, json=_device_payload("edge-files-binary-001"))
    assert created.status_code == 201
    device_id = created.json()["id"]
    payload = b"\x00\x01\x02\xffbinary-payload"

    uploaded = client.post(
        f"/api/devices/{device_id}/files/upload",
        headers=headers,
        data={"remote_path": "/opt/app/payload.bin"},
        files={"file": ("payload.bin", payload, "application/octet-stream")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["status"] == "uploaded"
    assert uploaded.json()["size"] == len(payload)

    downloaded = client.get(
        f"/api/devices/{device_id}/files/download?remote_path=/opt/app/payload.bin",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"].startswith("application/octet-stream")
    assert "payload.bin" in downloaded.headers["content-disposition"]
    assert downloaded.content == payload


def test_file_paths_cannot_escape_device_storage(client) -> None:
    headers = _auth_headers(client)
    created = client.post("/api/devices", headers=headers, json=_device_payload("edge-files-002"))
    assert created.status_code == 201

    response = client.post(
        f"/api/devices/{created.json()['id']}/files/upload",
        headers=headers,
        json={"remote_path": "/../secret.txt", "content": "nope"},
    )

    assert response.status_code == 400


def test_file_list_defaults_to_login_directory(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    created = client.post("/api/devices", headers=headers, json=_device_payload("edge-files-default-path"))
    requested_paths: list[str] = []

    def fake_list_files(self, device, remote_path):
        requested_paths.append(remote_path)
        return []

    monkeypatch.setattr(FileService, "list_files", fake_list_files)

    response = client.get(f"/api/devices/{created.json()['id']}/files", headers=headers)

    assert response.status_code == 200
    assert response.json()["path"] == "."
    assert requested_paths == ["."]


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (RemoteFileNotFoundError("."), 404, "远程目录不存在或无权访问: ."),
        (RemoteConnectionError("SSH 认证失败"), 502, "SSH 认证失败"),
    ],
)
def test_file_list_returns_actionable_remote_errors(
    client,
    monkeypatch,
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    headers = _auth_headers(client)
    created = client.post("/api/devices", headers=headers, json=_device_payload(f"edge-files-error-{expected_status}"))

    def fake_list_files(self, device, remote_path):
        raise error

    monkeypatch.setattr(FileService, "list_files", fake_list_files)

    response = client.get(f"/api/devices/{created.json()['id']}/files?path=.", headers=headers)

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail
