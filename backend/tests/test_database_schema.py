from sqlalchemy import inspect

from app.database import get_engine, init_db


def test_init_db_creates_wave1_schema(settings) -> None:
    init_db(settings)

    inspector = inspect(get_engine(settings))

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
