def _create_project(client, headers, *, code: str = "outside-bin") -> dict:
    response = client.post(
        "/api/projects",
        headers=headers,
        json={"code": code, "name": f"项目 {code}"},
    )
    assert response.status_code == 201
    return response.json()


def _create_function(client, headers, *, code: str = "outside-rubbish-bag") -> dict:
    response = client.post(
        "/api/functions",
        headers=headers,
        json={"code": code, "name": "桶外垃圾袋识别"},
    )
    assert response.status_code == 201
    return response.json()


def test_hardware_profiles_are_seeded(client, auth_headers) -> None:
    response = client.get("/api/hardware-profiles", headers=auth_headers)

    assert response.status_code == 200
    assert {item["code"] for item in response.json()["items"]} == {
        "rk3568-4g-debian11",
        "rk3588-8g-debian11",
    }


def test_project_and_function_generate_technical_codes_for_chinese_names(client, auth_headers) -> None:
    project = client.post(
        "/api/projects",
        headers=auth_headers,
        json={"name": "桶外识别项目"},
    )
    assert project.status_code == 201
    assert project.json()["name"] == "桶外识别项目"
    assert project.json()["code"].startswith("project-")

    edge_function = client.post(
        "/api/functions",
        headers=auth_headers,
        json={"name": "桶外垃圾袋识别"},
    )
    assert edge_function.status_code == 201
    assert edge_function.json()["name"] == "桶外垃圾袋识别"
    assert edge_function.json()["code"].startswith("function-")


def test_project_function_release_workflow_is_immutable_after_publish(client, auth_headers) -> None:
    project = _create_project(client, auth_headers)
    edge_function = _create_function(client, auth_headers)
    release_response = client.post(
        f"/api/functions/{edge_function['id']}/releases",
        headers=auth_headers,
        json={"version": "0.1.0", "manifest_json": {"schema_version": 1}},
    )
    assert release_response.status_code == 201
    release = release_response.json()

    profiles = client.get("/api/hardware-profiles", headers=auth_headers).json()["items"]
    variants = []
    for profile in profiles:
        variant = client.post(
            f"/api/functions/{edge_function['id']}/releases/{release['id']}/variants",
            headers=auth_headers,
            json={
                "hardware_profile_id": profile["id"],
                "artifact_uri": f"artifacts/outside-rubbish-bag/0.1.0/{profile['code']}.tar.gz",
                "artifact_sha256": "a" * 64,
                "artifact_size": 1024,
            },
        )
        assert variant.status_code == 201
        variants.append(variant.json())

    draft_update = client.put(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/variants/{variants[0]['id']}",
        headers=auth_headers,
        json={"artifact_sha256": "b" * 64, "artifact_size": 2048},
    )
    assert draft_update.status_code == 200
    assert draft_update.json()["artifact_sha256"] == "b" * 64

    unpublished_assignment = client.put(
        f"/api/projects/{project['id']}/functions/{edge_function['id']}",
        headers=auth_headers,
        json={"desired_release_id": release["id"]},
    )
    assert unpublished_assignment.status_code == 409

    published = client.post(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/publish",
        headers=auth_headers,
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    immutable = client.put(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}",
        headers=auth_headers,
        json={"release_notes": "should fail"},
    )
    assert immutable.status_code == 409

    immutable_variant = client.put(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/variants/{variants[0]['id']}",
        headers=auth_headers,
        json={"artifact_size": 4096},
    )
    assert immutable_variant.status_code == 409

    assignment = client.put(
        f"/api/projects/{project['id']}/functions/{edge_function['id']}",
        headers=auth_headers,
        json={"desired_release_id": release["id"], "config_json": {"camera": 0}},
    )
    assert assignment.status_code == 200
    assert assignment.json()["status"] == "active"

    pending_uninstall = client.post(
        f"/api/projects/{project['id']}/functions/{edge_function['id']}/pending-uninstall",
        headers=auth_headers,
    )
    assert pending_uninstall.status_code == 200
    assert pending_uninstall.json()["status"] == "pending_uninstall"


def test_device_accepts_formal_or_unassigned_project(client, auth_headers) -> None:
    project = _create_project(client, auth_headers, code="device-project")
    profile = client.get("/api/hardware-profiles", headers=auth_headers).json()["items"][0]

    assigned = client.post(
        "/api/devices",
        headers=auth_headers,
        json={
            "name": "assigned",
            "device_sn": "FORMAL-001",
            "project_id": project["id"],
            "expected_profile_id": profile["id"],
        },
    )
    assert assigned.status_code == 201
    assert assigned.json()["project_id"] == project["id"]
    assert assigned.json()["expected_profile_id"] == profile["id"]
    assert assigned.json()["device_uuid"]

    unassigned = client.post(
        "/api/devices",
        headers=auth_headers,
        json={"name": "pool", "device_sn": "FORMAL-002"},
    )
    assert unassigned.status_code == 201
    assert unassigned.json()["project_id"] is None

    free_text = client.post(
        "/api/devices",
        headers=auth_headers,
        json={"name": "legacy", "device_sn": "FORMAL-003", "project_id": "free-text"},
    )
    assert free_text.status_code == 422


def test_lifecycle_writes_require_admin(client, auth_headers) -> None:
    created = client.post(
        "/api/users",
        headers=auth_headers,
        json={"username": "lifecycle-operator", "password": "operator-pass", "role": "operator"},
    )
    assert created.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"username": "lifecycle-operator", "password": "operator-pass"},
    )
    operator_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/projects", headers=operator_headers).status_code == 200
    forbidden = client.post(
        "/api/projects",
        headers=operator_headers,
        json={"code": "operator-project", "name": "operator project"},
    )
    assert forbidden.status_code == 403
