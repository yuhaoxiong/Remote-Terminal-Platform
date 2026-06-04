from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_head_creates_wave1_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "migration.db"
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{db_path}"))
    assert set(inspector.get_table_names()) >= {
        "users",
        "devices",
        "groups",
        "device_metrics",
        "operation_logs",
        "update_tasks",
        "update_task_devices",
        "scheduled_tasks",
        "scheduled_task_runs",
        "alerts",
        "alert_rules",
        "alert_notification_channels",
        "alert_notification_policies",
        "alert_notification_deliveries",
        "port_pool",
    }
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    assert {"role", "is_active", "last_login_at", "last_login_ip", "password_changed_at"}.issubset(user_columns)
