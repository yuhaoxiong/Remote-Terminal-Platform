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
    assert downloaded.headers["content-type"].startswith("text/plain")
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
