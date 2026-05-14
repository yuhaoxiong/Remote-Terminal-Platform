import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.database import init_db
from app.main import create_app


def _settings(db_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{db_path}",
        jwt_secret_key="test-secret-key",
        default_admin_username="admin",
        default_admin_password="admin-pass",
    )


def test_init_db_migrates_legacy_update_task_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE update_tasks (
                id INTEGER PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                task_type VARCHAR(32) NOT NULL,
                command TEXT NOT NULL,
                rollback_command TEXT,
                target_filter JSON,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    settings = _settings(db_path)
    init_db(settings)

    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(update_tasks)").fetchall()}

    assert "failure_strategy" in columns
    assert "concurrency_limit" in columns

    with TestClient(create_app(settings)) as client:
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass"})
        assert login.status_code == 200
        response = client.get(
            "/api/update-tasks",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        assert response.status_code == 200
