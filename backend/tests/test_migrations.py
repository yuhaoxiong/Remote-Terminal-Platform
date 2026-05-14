from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_head_creates_wave1_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "migration.db"
    config = Config("alembic.ini")
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
        "port_pool",
    }
