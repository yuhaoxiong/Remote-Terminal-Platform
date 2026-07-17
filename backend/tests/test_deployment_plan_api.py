from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

from artifact_helpers import build_standard_package
from app.database import session_scope
from app.models.lifecycle import DeploymentPlan


def _prepare_deployment_context(client, headers, create_device, *, is_test_device: bool = False) -> dict:
    project = client.post(
        "/api/projects",
        headers=headers,
        json={"code": "deployment-project", "name": "部署测试项目"},
    ).json()
    edge_function = client.post(
        "/api/functions",
        headers=headers,
        json={"code": "deployment-function", "name": "部署测试功能"},
    ).json()
    release = client.post(
        f"/api/functions/{edge_function['id']}/releases",
        headers=headers,
        json={"version": "1.0.0"},
    ).json()
    profile = client.get("/api/hardware-profiles", headers=headers).json()["items"][0]
    package = build_standard_package(edge_function["code"], release["version"], profile["code"])
    variant = client.post(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/artifacts",
        headers=headers,
        data={"hardware_profile_id": str(profile["id"])},
        files={"file": ("deployment-function.tar.gz", package, "application/gzip")},
    ).json()
    published = client.post(
        f"/api/functions/{edge_function['id']}/releases/{release['id']}/publish",
        headers=headers,
    )
    assert published.status_code == 200
    assignment = client.put(
        f"/api/projects/{project['id']}/functions/{edge_function['id']}",
        headers=headers,
        json={"desired_release_id": release["id"], "config_json": {"camera": 0}},
    )
    assert assignment.status_code == 200
    device = create_device(
        name="部署测试设备",
        device_sn="DEPLOY-PLAN-001",
        project_id=project["id"],
        expected_profile_id=profile["id"],
        actual_profile_id=profile["id"],
        initialization_status="ready",
        is_test_device=is_test_device,
        status="online",
        ssh_port=12001,
    )
    return {
        "project": project,
        "function": edge_function,
        "release": release,
        "profile": profile,
        "variant": variant,
        "device": device,
    }


def test_admin_creates_24_hour_single_device_deployment_plan(
    client,
    auth_headers,
    create_device,
) -> None:
    context = _prepare_deployment_context(client, auth_headers, create_device)
    before = datetime.now(timezone.utc)

    response = client.post(
        f"/api/projects/{context['project']['id']}/deployment-plans",
        headers=auth_headers,
        json={"device_ids": [context["device"].id]},
    )

    assert response.status_code == 201, response.text
    plan = response.json()
    assert plan["project_id"] == context["project"]["id"]
    assert plan["status"] == "ready"
    assert len(plan["snapshot_hash"]) == 64
    expires_at = datetime.fromisoformat(plan["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    assert 23.9 * 3600 <= (expires_at - before).total_seconds() <= 24.1 * 3600
    assert len(plan["items"]) == 1
    item = plan["items"][0]
    assert item["device_id"] == context["device"].id
    assert item["function_id"] == context["function"]["id"]
    assert item["release_id"] == context["release"]["id"]
    assert item["variant_id"] == context["variant"]["id"]
    assert item["config_snapshot"] == {"camera": 0}
    assert item["artifact_sha256"] == context["variant"]["artifact_sha256"]
    assert item["status"] == "ready"
    assert item["preflight_json"]["ready"] is True
    assert item["preflight_json"]["hardware_profile_id"] == context["profile"]["id"]


def test_project_function_change_marks_plan_stale_and_blocks_confirmation(
    client,
    auth_headers,
    create_device,
) -> None:
    context = _prepare_deployment_context(client, auth_headers, create_device)
    plan = client.post(
        f"/api/projects/{context['project']['id']}/deployment-plans",
        headers=auth_headers,
        json={"device_ids": [context["device"].id]},
    ).json()
    changed = client.put(
        f"/api/projects/{context['project']['id']}/functions/{context['function']['id']}",
        headers=auth_headers,
        json={"desired_release_id": context["release"]["id"], "config_json": {"camera": 1}},
    )
    assert changed.status_code == 200

    confirmed = client.post(
        f"/api/deployment-plans/{plan['id']}/confirm",
        headers=auth_headers,
    )

    assert confirmed.status_code == 409
    assert "配置" in confirmed.json()["detail"]
    detail = client.get(f"/api/deployment-plans/{plan['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "stale"
    assert "配置" in detail.json()["stale_reason"]


def test_admin_confirmation_creates_one_idempotent_execution(
    client,
    auth_headers,
    create_device,
) -> None:
    context = _prepare_deployment_context(client, auth_headers, create_device)
    plan = client.post(
        f"/api/projects/{context['project']['id']}/deployment-plans",
        headers=auth_headers,
        json={"device_ids": [context["device"].id]},
    ).json()

    first = client.post(f"/api/deployment-plans/{plan['id']}/confirm", headers=auth_headers)
    second = client.post(f"/api/deployment-plans/{plan['id']}/confirm", headers=auth_headers)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    execution = first.json()
    assert execution["execution_id"]
    assert execution["plan_id"] == plan["id"]
    assert execution["status"] == "pending"
    assert len(execution["items"]) == 1
    assert execution["items"][0]["plan_item_id"] == plan["items"][0]["id"]
    assert execution["items"][0]["status"] == "pending"
    assert second.json()["execution_id"] == execution["execution_id"]
    detail = client.get(f"/api/deployment-plans/{plan['id']}", headers=auth_headers).json()
    assert detail["status"] == "confirmed"
    assert detail["confirmed_at"]


def test_expired_plan_cannot_be_confirmed(
    client,
    auth_headers,
    create_device,
    initialized_settings,
) -> None:
    context = _prepare_deployment_context(client, auth_headers, create_device)
    plan = client.post(
        f"/api/projects/{context['project']['id']}/deployment-plans",
        headers=auth_headers,
        json={"device_ids": [context["device"].id]},
    ).json()
    with session_scope(initialized_settings) as session:
        stored = session.get(DeploymentPlan, plan["id"])
        assert stored is not None
        stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    response = client.post(f"/api/deployment-plans/{plan['id']}/confirm", headers=auth_headers)

    assert response.status_code == 409
    assert "24 小时" in response.json()["detail"]
    detail = client.get(f"/api/deployment-plans/{plan['id']}", headers=auth_headers).json()
    assert detail["status"] == "expired"


def test_device_release_override_takes_precedence_in_deployment_plan(
    client,
    auth_headers,
    create_device,
) -> None:
    context = _prepare_deployment_context(client, auth_headers, create_device)
    override_release = client.post(
        f"/api/functions/{context['function']['id']}/releases",
        headers=auth_headers,
        json={"version": "1.1.0"},
    ).json()
    package = build_standard_package(
        context["function"]["code"],
        override_release["version"],
        context["profile"]["code"],
    )
    uploaded = client.post(
        f"/api/functions/{context['function']['id']}/releases/{override_release['id']}/artifacts",
        headers=auth_headers,
        data={"hardware_profile_id": str(context["profile"]["id"])},
        files={"file": ("override.tar.gz", package, "application/gzip")},
    )
    assert uploaded.status_code == 201
    published = client.post(
        f"/api/functions/{context['function']['id']}/releases/{override_release['id']}/publish",
        headers=auth_headers,
    )
    assert published.status_code == 200
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    override = client.put(
        f"/api/devices/{context['device'].id}/release-overrides/{context['function']['id']}",
        headers=auth_headers,
        json={
            "release_id": override_release["id"],
            "reason": "单设备现场验证",
            "expires_at": expires_at.isoformat(),
        },
    )
    assert override.status_code == 200, override.text
    plan = client.post(
        f"/api/projects/{context['project']['id']}/deployment-plans",
        headers=auth_headers,
        json={"device_ids": [context["device"].id]},
    )

    assert plan.status_code == 201, plan.text
    item = plan.json()["items"][0]
    assert item["release_id"] == override_release["id"]
    assert item["preflight_json"]["release_source"] == "device_override"
    assert item["preflight_json"]["override_reason"] == "单设备现场验证"
    confirmed = client.post(
        f"/api/deployment-plans/{plan.json()['id']}/confirm",
        headers=auth_headers,
    )
    assert confirmed.status_code == 200, confirmed.text


def test_offline_device_is_rejected_before_deployment_plan_creation(
    client,
    auth_headers,
    create_device,
) -> None:
    context = _prepare_deployment_context(client, auth_headers, create_device)
    updated = client.put(
        f"/api/devices/{context['device'].id}",
        headers=auth_headers,
        json={"status": "offline"},
    )
    assert updated.status_code == 200, updated.text

    response = client.post(
        f"/api/projects/{context['project']['id']}/deployment-plans",
        headers=auth_headers,
        json={"device_ids": [context["device"].id]},
    )

    assert response.status_code == 409
    assert "不在线" in response.json()["detail"]


def test_operator_can_read_plan_but_cannot_confirm_it(
    client,
    auth_headers,
    create_device,
) -> None:
    context = _prepare_deployment_context(client, auth_headers, create_device)
    plan = client.post(
        f"/api/projects/{context['project']['id']}/deployment-plans",
        headers=auth_headers,
        json={"device_ids": [context["device"].id]},
    ).json()
    execution = client.post(
        f"/api/deployment-plans/{plan['id']}/confirm",
        headers=auth_headers,
    ).json()
    created = client.post(
        "/api/users",
        headers=auth_headers,
        json={"username": "deployment-operator", "password": "operator-pass", "role": "operator"},
    )
    assert created.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"username": "deployment-operator", "password": "operator-pass"},
    )
    operator_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    detail = client.get(f"/api/deployment-plans/{plan['id']}", headers=operator_headers)
    execution_detail = client.get(
        f"/api/deployment-executions/{execution['execution_id']}",
        headers=operator_headers,
    )
    confirmation = client.post(
        f"/api/deployment-plans/{plan['id']}/confirm",
        headers=operator_headers,
    )

    assert detail.status_code == 200
    assert detail.json()["id"] == plan["id"]
    assert execution_detail.status_code == 200
    assert execution_detail.json()["execution_id"] == execution["execution_id"]
    assert confirmation.status_code == 403


def test_multi_device_plan_confirmation_is_independent_of_request_order(
    client,
    auth_headers,
    create_device,
) -> None:
    context = _prepare_deployment_context(client, auth_headers, create_device)
    second_device = create_device(
        name="部署测试设备 2",
        device_sn="DEPLOY-PLAN-002",
        project_id=context["project"]["id"],
        expected_profile_id=context["profile"]["id"],
        actual_profile_id=context["profile"]["id"],
        initialization_status="ready",
        status="online",
        ssh_port=12002,
    )
    plan = client.post(
        f"/api/projects/{context['project']['id']}/deployment-plans",
        headers=auth_headers,
        json={"device_ids": [second_device.id, context["device"].id]},
    )
    assert plan.status_code == 201, plan.text

    confirmation = client.post(
        f"/api/deployment-plans/{plan.json()['id']}/confirm",
        headers=auth_headers,
    )

    assert confirmation.status_code == 200, confirmation.text
    assert len(confirmation.json()["items"]) == 2


def test_admin_executes_confirmed_deployment_and_records_success(
    client,
    auth_headers,
    create_device,
    fake_ssh_service,
) -> None:
    client.app.state.settings.bootstrap_platform_url = "https://platform.example.test"
    context = _prepare_deployment_context(client, auth_headers, create_device)
    plan = client.post(
        f"/api/projects/{context['project']['id']}/deployment-plans",
        headers=auth_headers,
        json={"device_ids": [context["device"].id]},
    ).json()
    execution = client.post(
        f"/api/deployment-plans/{plan['id']}/confirm",
        headers=auth_headers,
    ).json()
    fake_ssh = fake_ssh_service()
    fake_ssh.result = (
        0,
        json.dumps(
            {
                "schema_version": 1,
                "execution_id": execution["execution_id"],
                "function_code": context["function"]["code"],
                "status": "succeeded",
                "changed": True,
                "rollback_performed": False,
                "steps": {"healthcheck": "succeeded"},
            }
        ),
        "",
    )
    client.app.state.ssh_service = fake_ssh

    response = client.post(
        f"/api/deployment-executions/{execution['execution_id']}/execute",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["execution_id"] == execution["execution_id"]
    assert body["status"] == "completed"
    assert body["started_at"]
    assert body["finished_at"]
    assert len(body["items"]) == 1
    assert body["items"][0]["status"] == "success"
    assert body["items"][0]["attempt_count"] == 1
    assert body["items"][0]["result_json"]["steps"]["healthcheck"] == "succeeded"
    assert fake_ssh.calls[0][2] == 1800
    repeated = client.post(
        f"/api/deployment-executions/{execution['execution_id']}/execute",
        headers=auth_headers,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == body
    assert len(fake_ssh.calls) == 1


def test_device_downloads_only_its_execution_artifact_with_short_lived_token(
    client,
    auth_headers,
    create_device,
    fake_ssh_service,
) -> None:
    client.app.state.settings.bootstrap_platform_url = "https://platform.example.test"
    context = _prepare_deployment_context(client, auth_headers, create_device)
    plan = client.post(
        f"/api/projects/{context['project']['id']}/deployment-plans",
        headers=auth_headers,
        json={"device_ids": [context["device"].id]},
    ).json()
    execution = client.post(
        f"/api/deployment-plans/{plan['id']}/confirm",
        headers=auth_headers,
    ).json()
    fake_ssh = fake_ssh_service(
        (
            0,
            json.dumps(
                {
                    "schema_version": 1,
                    "execution_id": execution["execution_id"],
                    "function_code": context["function"]["code"],
                    "status": "succeeded",
                    "changed": True,
                    "rollback_performed": False,
                    "steps": {"healthcheck": "succeeded"},
                }
            ),
            "",
        )
    )
    client.app.state.ssh_service = fake_ssh
    started = client.post(
        f"/api/deployment-executions/{execution['execution_id']}/execute",
        headers=auth_headers,
    )
    assert started.status_code == 200, started.text
    command = fake_ssh.calls[0][1]
    assert command == "sudo -n /usr/local/bin/edge-deploy apply --stdin"
    assert "artifact_token" not in command
    encoded = fake_ssh.input_calls[0]
    descriptor = json.loads(base64.b64decode(encoded).decode("utf-8"))
    assert len(descriptor["deployment_fingerprint"]) == 64

    artifact_path = descriptor["artifact_url"].removeprefix("https://platform.example.test")
    downloaded = client.get(
        artifact_path,
        headers={"Authorization": f"Bearer {descriptor['artifact_token']}"},
    )
    rejected = client.get(
        artifact_path,
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert downloaded.status_code == 200
    assert downloaded.headers["etag"] == f'"{context["variant"]["artifact_sha256"]}"'
    assert rejected.status_code == 401


def test_production_deployment_failure_records_automatic_rollback(
    client,
    auth_headers,
    create_device,
    fake_ssh_service,
) -> None:
    client.app.state.settings.bootstrap_platform_url = "https://platform.example.test"
    context = _prepare_deployment_context(client, auth_headers, create_device)
    plan = client.post(
        f"/api/projects/{context['project']['id']}/deployment-plans",
        headers=auth_headers,
        json={"device_ids": [context["device"].id]},
    ).json()
    execution = client.post(
        f"/api/deployment-plans/{plan['id']}/confirm",
        headers=auth_headers,
    ).json()
    failure = {
        "schema_version": 1,
        "execution_id": execution["execution_id"],
        "function_code": context["function"]["code"],
        "status": "failed",
        "changed": True,
        "message": "healthcheck failed",
        "rollback_performed": True,
        "steps": {"healthcheck": "failed", "rollback": "succeeded"},
    }
    fake_ssh = fake_ssh_service((1, json.dumps(failure), "healthcheck failed"))
    client.app.state.ssh_service = fake_ssh

    response = client.post(
        f"/api/deployment-executions/{execution['execution_id']}/execute",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "failed"
    assert body["items"][0]["status"] == "rolled_back"
    assert body["items"][0]["result_json"]["rollback_performed"] is True
    descriptor = json.loads(base64.b64decode(fake_ssh.input_calls[0]).decode("utf-8"))
    assert descriptor["rollback_on_failure"] is True


def test_test_device_failure_preserves_failed_state_without_rollback(
    client,
    auth_headers,
    create_device,
    fake_ssh_service,
) -> None:
    client.app.state.settings.bootstrap_platform_url = "https://platform.example.test"
    context = _prepare_deployment_context(
        client,
        auth_headers,
        create_device,
        is_test_device=True,
    )
    plan = client.post(
        f"/api/projects/{context['project']['id']}/deployment-plans",
        headers=auth_headers,
        json={"device_ids": [context["device"].id]},
    ).json()
    execution = client.post(
        f"/api/deployment-plans/{plan['id']}/confirm",
        headers=auth_headers,
    ).json()
    failure = {
        "schema_version": 1,
        "execution_id": execution["execution_id"],
        "function_code": context["function"]["code"],
        "status": "failed",
        "changed": True,
        "message": "healthcheck failed",
        "rollback_performed": False,
        "steps": {"healthcheck": "failed"},
    }
    fake_ssh = fake_ssh_service((1, json.dumps(failure), "healthcheck failed"))
    client.app.state.ssh_service = fake_ssh

    response = client.post(
        f"/api/deployment-executions/{execution['execution_id']}/execute",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "failed"
    assert response.json()["items"][0]["status"] == "failed"
    assert response.json()["items"][0]["result_json"]["rollback_performed"] is False
    descriptor = json.loads(base64.b64decode(fake_ssh.input_calls[0]).decode("utf-8"))
    assert descriptor["rollback_on_failure"] is False


def test_multi_function_execution_isolated_results_become_partial_failure(
    client,
    auth_headers,
    create_device,
    fake_ssh_service,
) -> None:
    client.app.state.settings.bootstrap_platform_url = "https://platform.example.test"
    context = _prepare_deployment_context(client, auth_headers, create_device)
    second_function = client.post(
        "/api/functions",
        headers=auth_headers,
        json={"code": "deployment-function-two", "name": "部署测试功能二"},
    ).json()
    second_release = client.post(
        f"/api/functions/{second_function['id']}/releases",
        headers=auth_headers,
        json={"version": "2.0.0"},
    ).json()
    package = build_standard_package(
        second_function["code"],
        second_release["version"],
        context["profile"]["code"],
    )
    uploaded = client.post(
        f"/api/functions/{second_function['id']}/releases/{second_release['id']}/artifacts",
        headers=auth_headers,
        data={"hardware_profile_id": str(context["profile"]["id"])},
        files={"file": ("deployment-function-two.tar.gz", package, "application/gzip")},
    )
    assert uploaded.status_code == 201
    assert client.post(
        f"/api/functions/{second_function['id']}/releases/{second_release['id']}/publish",
        headers=auth_headers,
    ).status_code == 200
    assert client.put(
        f"/api/projects/{context['project']['id']}/functions/{second_function['id']}",
        headers=auth_headers,
        json={"desired_release_id": second_release["id"], "config_json": {}},
    ).status_code == 200
    plan = client.post(
        f"/api/projects/{context['project']['id']}/deployment-plans",
        headers=auth_headers,
        json={"device_ids": [context["device"].id]},
    ).json()
    execution = client.post(
        f"/api/deployment-plans/{plan['id']}/confirm",
        headers=auth_headers,
    ).json()
    results = [
        (
            0,
            json.dumps({
                "schema_version": 1,
                "execution_id": execution["execution_id"],
                "function_code": context["function"]["code"],
                "status": "succeeded",
                "changed": True,
                "rollback_performed": False,
                "steps": {},
            }),
            "",
        ),
        (
            1,
            json.dumps({
                "schema_version": 1,
                "execution_id": execution["execution_id"],
                "function_code": second_function["code"],
                "status": "failed",
                "changed": True,
                "message": "start failed",
                "rollback_performed": True,
                "steps": {},
            }),
            "start failed",
        ),
    ]
    fake_ssh = fake_ssh_service()

    def execute_with_input(device, command, input_text, timeout_seconds):
        fake_ssh.calls.append((device, command, timeout_seconds))
        fake_ssh.input_calls.append(input_text)
        return results.pop(0)

    fake_ssh.execute_with_input = execute_with_input
    client.app.state.ssh_service = fake_ssh

    response = client.post(
        f"/api/deployment-executions/{execution['execution_id']}/execute",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "partial_failed"
    assert [item["status"] for item in response.json()["items"]] == ["success", "rolled_back"]
    assert len(fake_ssh.calls) == 2
