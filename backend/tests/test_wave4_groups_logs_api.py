from app.database import session_scope
from app.models.log import OperationLog


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-pass"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _device_payload(device_sn: str, *, project_id: str, group_id: int | None, tags: list[str]) -> dict[str, object]:
    return {
        "name": f"Device {device_sn}",
        "device_sn": device_sn,
        "project_id": project_id,
        "location": "Line 1",
        "hardware_model": "IPC-3000",
        "ssh_user": "root",
        "local_ip": "192.168.10.21",
        "tags": tags,
        "group_id": group_id,
    }


def test_group_crud_device_filters_and_log_csv_export(client, initialized_settings) -> None:
    headers = _auth_headers(client)

    created_group = client.post(
        "/api/groups",
        headers=headers,
        json={"name": "Factory A", "description": "North site"},
    )
    assert created_group.status_code == 201
    group_id = created_group.json()["id"]

    child_group = client.post(
        "/api/groups",
        headers=headers,
        json={"name": "Line 1", "parent_id": group_id},
    )
    assert child_group.status_code == 201

    listed_groups = client.get("/api/groups", headers=headers)
    assert listed_groups.status_code == 200
    assert [group["name"] for group in listed_groups.json()["items"]] == ["Factory A", "Line 1"]

    first = client.post(
        "/api/devices",
        headers=headers,
        json=_device_payload("edge-filter-001", project_id="factory-a", group_id=group_id, tags=["vision", "prod"]),
    )
    assert first.status_code == 201
    second = client.post(
        "/api/devices",
        headers=headers,
        json=_device_payload("edge-filter-002", project_id="factory-b", group_id=None, tags=["audio"]),
    )
    assert second.status_code == 201

    filtered = client.get(f"/api/devices?project_id=factory-a&group_id={group_id}&tag=vision", headers=headers)
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["device_sn"] == "edge-filter-001"

    client.put(f"/api/groups/{group_id}", headers=headers, json={"description": "Updated site"})
    deleted = client.delete(f"/api/groups/{child_group.json()['id']}", headers=headers)
    assert deleted.status_code == 204

    with session_scope(initialized_settings) as session:
        session.add(
            OperationLog(
                user_id=1,
                action="audit.test",
                target_type="device",
                target_id=first.json()["id"],
                status="success",
                detail="=csv row",
            )
        )

    logs = client.get("/api/logs?action=audit.test", headers=headers)
    assert logs.status_code == 200
    assert logs.json()["total"] == 1
    assert logs.json()["items"][0]["detail"] == "=csv row"

    exported = client.get("/api/logs/export?action=audit.test", headers=headers)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert exported.headers["content-disposition"] == 'attachment; filename="operation_logs.csv"'
    assert exported.headers["x-content-type-options"] == "nosniff"
    assert "audit.test" in exported.text
    assert "\t=csv row" in exported.text
