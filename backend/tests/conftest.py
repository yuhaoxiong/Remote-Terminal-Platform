from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import init_db, session_scope
from app.main import create_app
from app.models.device import Device
from app.models.group import Group
from app.models.update_task import UpdateTask, UpdateTaskDevice


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        jwt_secret_key="test-secret-key",
        default_admin_username="admin",
        default_admin_password="admin-pass",
    )


@pytest.fixture()
def initialized_settings(settings: Settings) -> Settings:
    init_db(settings)
    return settings


@pytest.fixture()
def client(initialized_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(initialized_settings)) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def create_group(initialized_settings: Settings):
    def _create_group(name: str = "测试分组", description: str = "测试分组") -> Group:
        with session_scope(initialized_settings) as session:
            group = Group(name=name, description=description)
            session.add(group)
            session.flush()
            session.refresh(group)
            group_id = group.id
        with session_scope(initialized_settings) as session:
            return session.get(Group, group_id)

    return _create_group


@pytest.fixture()
def create_device(initialized_settings: Settings):
    def _create_device(
        *,
        name: str = "测试设备",
        device_sn: str = "SN-TEST-001",
        project_id: str = "test-project",
        group_id: int | None = None,
        status: str = "online",
        ssh_port: int | None = 12001,
        ssh_user: str = "ztl",
        ssh_auth_type: str = "password",
        ssh_password_encrypted: str | None = "123456",
        tags: list[str] | None = None,
    ) -> Device:
        with session_scope(initialized_settings) as session:
            device = Device(
                name=name,
                device_sn=device_sn,
                project_id=project_id,
                group_id=group_id,
                status=status,
                ssh_port=ssh_port,
                ssh_user=ssh_user,
                ssh_auth_type=ssh_auth_type,
                ssh_password_encrypted=ssh_password_encrypted,
                tags=tags or [],
            )
            session.add(device)
            session.flush()
            session.refresh(device)
            device_id = device.id
        with session_scope(initialized_settings) as session:
            return session.get(Device, device_id)

    return _create_device


@pytest.fixture()
def create_update_task(initialized_settings: Settings, create_device):
    def _create_update_task(
        *,
        name: str = "测试任务",
        command: str = "hostname",
        execution_mode: str = "dry_run",
        failure_strategy: str = "continue",
        device_ids: list[int] | None = None,
    ) -> UpdateTask:
        if not device_ids:
            device = create_device()
            device_ids = [device.id]
        with session_scope(initialized_settings) as session:
            task = UpdateTask(
                name=name,
                task_type="command",
                command=command,
                target_filter={"device_ids": device_ids},
                execution_mode=execution_mode,
                failure_strategy=failure_strategy,
                concurrency_limit=5,
            )
            session.add(task)
            session.flush()
            for device_id in device_ids:
                session.add(UpdateTaskDevice(task_id=task.id, device_id=device_id, status="pending"))
            session.flush()
            session.refresh(task)
            task_id = task.id
        with session_scope(initialized_settings) as session:
            return session.get(UpdateTask, task_id)

    return _create_update_task


@pytest.fixture()
def fake_ssh_service():
    class FakeSshService:
        def __init__(self, result: tuple[int, str, str] = (0, "ok", "")) -> None:
            self.result = result
            self.calls: list[tuple[Device, str, int]] = []

        def execute(self, device: Device, command: str, timeout_seconds: int) -> tuple[int, str, str]:
            self.calls.append((device, command, timeout_seconds))
            return self.result

    return FakeSshService
