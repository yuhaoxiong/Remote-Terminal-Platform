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
        scheduler_enabled=False,
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
        connection.execute(
            """
            CREATE TABLE update_task_devices (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                device_id INTEGER NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                output_summary TEXT,
                started_at DATETIME,
                finished_at DATETIME
            )
            """
        )

    settings = _settings(db_path)
    init_db(settings)

    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(update_tasks)").fetchall()}
        device_columns = {row[1] for row in connection.execute("PRAGMA table_info(update_task_devices)").fetchall()}

    assert "failure_strategy" in columns
    assert "concurrency_limit" in columns
    assert "execution_mode" in columns
    assert {"exit_code", "stdout_summary", "stderr_summary", "error_message"}.issubset(device_columns)

    with TestClient(create_app(settings)) as client:
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass"})
        assert login.status_code == 200
        response = client.get(
            "/api/update-tasks",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        assert response.status_code == 200


def test_init_db_migrates_legacy_device_credential_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-devices.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE devices (
                id INTEGER PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                device_sn VARCHAR(120) NOT NULL UNIQUE,
                project_id VARCHAR(120) NOT NULL,
                location VARCHAR(255),
                hardware_model VARCHAR(120),
                ssh_port INTEGER UNIQUE,
                vnc_port INTEGER UNIQUE,
                local_ip VARCHAR(64),
                os_version VARCHAR(120),
                description TEXT,
                tags JSON,
                group_id INTEGER,
                status VARCHAR(32) NOT NULL DEFAULT 'unknown',
                last_seen DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            "INSERT INTO devices (name, device_sn, project_id, ssh_port, status) VALUES ('legacy', 'legacy-1', 'factory', 12001, 'unknown')"
        )

    settings = _settings(db_path)
    init_db(settings)

    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(devices)").fetchall()}
        device = connection.execute(
            "SELECT ssh_user, ssh_auth_type, ssh_password_encrypted FROM devices WHERE device_sn = 'legacy-1'"
        ).fetchone()

    assert {"ssh_user", "ssh_auth_type", "ssh_password_encrypted", "ssh_key_encrypted"}.issubset(columns)
    assert device == ("ztl", "password", "123456")


def test_init_db_migrates_legacy_scheduled_task_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-scheduled.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE scheduled_tasks (
                id INTEGER PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                task_type VARCHAR(32) NOT NULL,
                schedule VARCHAR(120) NOT NULL,
                command TEXT,
                target_filter JSON,
                enabled BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    init_db(_settings(db_path))

    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(scheduled_tasks)").fetchall()}
        run_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'scheduled_task_runs'"
            ).fetchall()
        }

    assert {
        "execution_mode",
        "failure_strategy",
        "concurrency_limit",
        "last_run_at",
        "last_status",
        "last_error",
        "next_run_at",
        "running",
    }.issubset(columns)
    assert run_tables == {"scheduled_task_runs"}


def test_init_db_creates_default_alert_rules(tmp_path: Path) -> None:
    db_path = tmp_path / "alerts.db"
    init_db(_settings(db_path))

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ('alerts', 'alert_rules')"
            ).fetchall()
        }
        rules = {row[0]: row[1] for row in connection.execute("SELECT rule_type, enabled FROM alert_rules").fetchall()}

    assert tables == {"alerts", "alert_rules"}
    assert {
        "device_status",
        "cpu_high",
        "memory_high",
        "disk_high",
        "metrics_stale",
        "scheduled_task_failed",
        "update_task_failed",
    }.issubset(rules)


def test_init_db_creates_alert_notification_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "alert-notifications.db"
    init_db(_settings(db_path))

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table'
                AND name IN (
                    'alert_notification_channels',
                    'alert_notification_policies',
                    'alert_notification_deliveries'
                )
                """
            ).fetchall()
        }

    assert tables == {
        "alert_notification_channels",
        "alert_notification_policies",
        "alert_notification_deliveries",
    }
