from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_alembic_upgrade_head_creates_wave1_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "migration.db"
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
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
        "projects",
        "hardware_profiles",
        "functions",
        "function_releases",
        "function_variants",
        "project_functions",
        "device_release_overrides",
        "deployment_plans",
        "deployment_plan_items",
        "deployment_executions",
        "deployment_execution_items",
    }
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    assert {"role", "is_active", "last_login_at", "last_login_ip", "password_changed_at"}.issubset(user_columns)
    device_columns = {column["name"] for column in inspector.get_columns("devices")}
    assert {
        "device_uuid",
        "project_id",
        "expected_profile_id",
        "actual_profile_id",
        "device_role",
        "is_test_device",
    }.issubset(device_columns)
    with engine.connect() as connection:
        profile_codes = set(connection.execute(text("SELECT code FROM hardware_profiles")).scalars())
    assert profile_codes == {"rk3568-4g-debian11", "rk3588-8g-debian11"}
