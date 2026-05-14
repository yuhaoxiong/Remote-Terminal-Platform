from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import init_db
from app.main import create_app


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
