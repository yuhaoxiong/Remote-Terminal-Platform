from __future__ import annotations

import hashlib

from artifact_helpers import build_standard_package


def _create_function_release(client, headers) -> tuple[dict, dict, dict]:
    edge_function = client.post(
        "/api/functions",
        headers=headers,
        json={"code": "artifact-test", "name": "制品测试功能"},
    ).json()
    release = client.post(
        f"/api/functions/{edge_function['id']}/releases",
        headers=headers,
        json={"version": "0.1.0"},
    ).json()
    profile = client.get("/api/hardware-profiles", headers=headers).json()["items"][0]
    return edge_function, release, profile


def test_admin_uploads_standard_package_with_server_calculated_digest(client, auth_headers) -> None:
    edge_function, release, profile = _create_function_release(client, auth_headers)
    package = build_standard_package(edge_function["code"], release["version"], profile["code"])

    response = client.post(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/artifacts",
        headers=auth_headers,
        data={"hardware_profile_id": str(profile["id"])},
        files={"file": ("artifact-test.tar.gz", package, "application/gzip")},
    )

    assert response.status_code == 201, response.text
    variant = response.json()
    assert variant["hardware_profile_id"] == profile["id"]
    assert variant["artifact_size"] == len(package)
    assert variant["artifact_sha256"] == hashlib.sha256(package).hexdigest()
    assert variant["artifact_uri"].startswith("artifacts/")

    listed = client.get(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/variants",
        headers=auth_headers,
    )
    assert listed.status_code == 200
    assert listed.json()["items"] == [variant]


def test_authenticated_user_downloads_uploaded_artifact(client, auth_headers) -> None:
    edge_function, release, profile = _create_function_release(client, auth_headers)
    package = build_standard_package(edge_function["code"], release["version"], profile["code"])
    variant = client.post(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/artifacts",
        headers=auth_headers,
        data={"hardware_profile_id": str(profile["id"])},
        files={"file": ("artifact-test.tar.gz", package, "application/gzip")},
    ).json()

    response = client.get(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/variants/{variant['id']}/artifact",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.content == package
    assert response.headers["etag"] == f'"{variant["artifact_sha256"]}"'
    assert response.headers["accept-ranges"] == "bytes"
    assert "attachment" in response.headers["content-disposition"]


def test_artifact_download_supports_byte_ranges(client, auth_headers) -> None:
    edge_function, release, profile = _create_function_release(client, auth_headers)
    package = build_standard_package(edge_function["code"], release["version"], profile["code"])
    variant = client.post(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/artifacts",
        headers=auth_headers,
        data={"hardware_profile_id": str(profile["id"])},
        files={"file": ("artifact-test.tar.gz", package, "application/gzip")},
    ).json()

    response = client.get(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/variants/{variant['id']}/artifact",
        headers={**auth_headers, "Range": "bytes=10-19"},
    )

    assert response.status_code == 206
    assert response.content == package[10:20]
    assert response.headers["content-range"] == f"bytes 10-19/{len(package)}"


def test_release_cannot_publish_manually_registered_missing_artifact(client, auth_headers) -> None:
    edge_function, release, profile = _create_function_release(client, auth_headers)
    registered = client.post(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/variants",
        headers=auth_headers,
        json={
            "hardware_profile_id": profile["id"],
            "artifact_uri": "artifacts/missing.tar.gz",
            "artifact_sha256": "a" * 64,
            "artifact_size": 1024,
        },
    )
    assert registered.status_code == 201

    response = client.post(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/publish",
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert "平台制品仓库" in response.json()["detail"]


def test_upload_rejects_package_without_healthcheck_and_creates_no_variant(client, auth_headers) -> None:
    edge_function, release, profile = _create_function_release(client, auth_headers)
    package = build_standard_package(
        edge_function["code"],
        release["version"],
        profile["code"],
        omit_paths={"scripts/healthcheck.sh"},
    )

    response = client.post(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/artifacts",
        headers=auth_headers,
        data={"hardware_profile_id": str(profile["id"])},
        files={"file": ("invalid.tar.gz", package, "application/gzip")},
    )

    assert response.status_code == 422
    assert "scripts/healthcheck.sh" in response.json()["detail"]
    listed = client.get(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/variants",
        headers=auth_headers,
    )
    assert listed.json() == {"total": 0, "items": []}


def test_draft_artifact_can_be_replaced_but_published_artifact_is_immutable(client, auth_headers) -> None:
    edge_function, release, profile = _create_function_release(client, auth_headers)
    first_package = build_standard_package(
        edge_function["code"], release["version"], profile["code"], artifact_content=b"print('first')\n"
    )
    second_package = build_standard_package(
        edge_function["code"], release["version"], profile["code"], artifact_content=b"print('second')\n"
    )
    endpoint = f"/api/functions/{edge_function['id']}/releases/{release['id']}/artifacts"

    first = client.post(
        endpoint,
        headers=auth_headers,
        data={"hardware_profile_id": str(profile["id"])},
        files={"file": ("first.tar.gz", first_package, "application/gzip")},
    ).json()
    second_response = client.post(
        endpoint,
        headers=auth_headers,
        data={"hardware_profile_id": str(profile["id"])},
        files={"file": ("second.tar.gz", second_package, "application/gzip")},
    )

    assert second_response.status_code == 201
    second = second_response.json()
    assert second["id"] == first["id"]
    assert second["artifact_sha256"] != first["artifact_sha256"]
    published = client.post(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/publish",
        headers=auth_headers,
    )
    assert published.status_code == 200

    immutable = client.post(
        endpoint,
        headers=auth_headers,
        data={"hardware_profile_id": str(profile["id"])},
        files={"file": ("third.tar.gz", first_package, "application/gzip")},
    )
    assert immutable.status_code == 409


def test_operator_cannot_upload_function_artifact(client, auth_headers) -> None:
    edge_function, release, profile = _create_function_release(client, auth_headers)
    created = client.post(
        "/api/users",
        headers=auth_headers,
        json={"username": "artifact-operator", "password": "operator-pass", "role": "operator"},
    )
    assert created.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"username": "artifact-operator", "password": "operator-pass"},
    )
    operator_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    package = build_standard_package(edge_function["code"], release["version"], profile["code"])

    response = client.post(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/artifacts",
        headers=operator_headers,
        data={"hardware_profile_id": str(profile["id"])},
        files={"file": ("operator.tar.gz", package, "application/gzip")},
    )

    assert response.status_code == 403
