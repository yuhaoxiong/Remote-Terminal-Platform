from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


_engines: dict[str, Engine] = {}
_sessionmakers: dict[str, sessionmaker[Session]] = {}


def get_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    database_url = settings.database_url
    if database_url not in _engines:
        if database_url.startswith("sqlite:///"):
            db_path = Path(database_url.replace("sqlite:///", "", 1))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        _engines[database_url] = create_engine(
            database_url,
            connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        )
    return _engines[database_url]


def get_sessionmaker(settings: Settings | None = None) -> sessionmaker[Session]:
    settings = settings or get_settings()
    database_url = settings.database_url
    if database_url not in _sessionmakers:
        _sessionmakers[database_url] = sessionmaker(
            bind=get_engine(settings),
            autoflush=False,
            expire_on_commit=False,
        )
    return _sessionmakers[database_url]


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    session = get_sessionmaker(settings)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _ensure_sqlite_schema(settings: Settings) -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    engine = get_engine(settings)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "update_tasks" in table_names:
            update_task_columns = {column["name"] for column in inspector.get_columns("update_tasks")}
            if "execution_mode" not in update_task_columns:
                connection.execute(
                    text("ALTER TABLE update_tasks ADD COLUMN execution_mode VARCHAR(32) NOT NULL DEFAULT 'dry_run'")
                )
            if "failure_strategy" not in update_task_columns:
                connection.execute(
                    text("ALTER TABLE update_tasks ADD COLUMN failure_strategy VARCHAR(32) NOT NULL DEFAULT 'continue'")
                )
            if "concurrency_limit" not in update_task_columns:
                connection.execute(text("ALTER TABLE update_tasks ADD COLUMN concurrency_limit INTEGER NOT NULL DEFAULT 5"))

        if "update_task_devices" in table_names:
            update_task_device_columns = {column["name"] for column in inspector.get_columns("update_task_devices")}
            if "exit_code" not in update_task_device_columns:
                connection.execute(text("ALTER TABLE update_task_devices ADD COLUMN exit_code INTEGER"))
            if "stdout_summary" not in update_task_device_columns:
                connection.execute(text("ALTER TABLE update_task_devices ADD COLUMN stdout_summary TEXT"))
            if "stderr_summary" not in update_task_device_columns:
                connection.execute(text("ALTER TABLE update_task_devices ADD COLUMN stderr_summary TEXT"))
            if "error_message" not in update_task_device_columns:
                connection.execute(text("ALTER TABLE update_task_devices ADD COLUMN error_message TEXT"))

        if "devices" in table_names:
            device_columns = {column["name"] for column in inspector.get_columns("devices")}
            if "ssh_user" not in device_columns:
                connection.execute(text("ALTER TABLE devices ADD COLUMN ssh_user VARCHAR(64) NOT NULL DEFAULT 'ztl'"))
            else:
                connection.execute(text("UPDATE devices SET ssh_user = 'ztl' WHERE ssh_user IS NULL OR ssh_user = ''"))
            if "ssh_auth_type" not in device_columns:
                connection.execute(text("ALTER TABLE devices ADD COLUMN ssh_auth_type VARCHAR(32) NOT NULL DEFAULT 'password'"))
            if "ssh_password_encrypted" not in device_columns:
                connection.execute(text("ALTER TABLE devices ADD COLUMN ssh_password_encrypted TEXT"))
            if "ssh_key_encrypted" not in device_columns:
                connection.execute(text("ALTER TABLE devices ADD COLUMN ssh_key_encrypted TEXT"))
            connection.execute(text("UPDATE devices SET ssh_password_encrypted = '123456' WHERE ssh_password_encrypted IS NULL OR ssh_password_encrypted = ''"))

        if "scheduled_tasks" in table_names:
            scheduled_task_columns = {column["name"] for column in inspector.get_columns("scheduled_tasks")}
            if "execution_mode" not in scheduled_task_columns:
                connection.execute(text("ALTER TABLE scheduled_tasks ADD COLUMN execution_mode VARCHAR(32) NOT NULL DEFAULT 'dry_run'"))
            if "failure_strategy" not in scheduled_task_columns:
                connection.execute(text("ALTER TABLE scheduled_tasks ADD COLUMN failure_strategy VARCHAR(32) NOT NULL DEFAULT 'continue'"))
            if "concurrency_limit" not in scheduled_task_columns:
                connection.execute(text("ALTER TABLE scheduled_tasks ADD COLUMN concurrency_limit INTEGER NOT NULL DEFAULT 5"))
            if "last_run_at" not in scheduled_task_columns:
                connection.execute(text("ALTER TABLE scheduled_tasks ADD COLUMN last_run_at DATETIME"))
            if "last_status" not in scheduled_task_columns:
                connection.execute(text("ALTER TABLE scheduled_tasks ADD COLUMN last_status VARCHAR(32)"))
            if "last_error" not in scheduled_task_columns:
                connection.execute(text("ALTER TABLE scheduled_tasks ADD COLUMN last_error TEXT"))
            if "next_run_at" not in scheduled_task_columns:
                connection.execute(text("ALTER TABLE scheduled_tasks ADD COLUMN next_run_at DATETIME"))
            if "running" not in scheduled_task_columns:
                connection.execute(text("ALTER TABLE scheduled_tasks ADD COLUMN running BOOLEAN NOT NULL DEFAULT 0"))


def init_db(settings: Settings | None = None) -> None:
    from app.migrations import upgrade_to_head
    from app.models.alert import Alert, AlertRule
    from app.models.device import Device
    from app.models.group import Group
    from app.models.log import OperationLog
    from app.models.metric import DeviceMetric
    from app.models.port_pool import PortPool
    from app.models.scheduled_task import ScheduledTask, ScheduledTaskRun
    from app.models.update_task import UpdateTask, UpdateTaskDevice, UpdateTaskTemplate
    from app.models.user import User
    from app.services.alert_service import AlertService
    from app.services.security import hash_password

    settings = settings or get_settings()
    upgrade_to_head(settings)
    Base.metadata.create_all(get_engine(settings))
    _ensure_sqlite_schema(settings)

    with session_scope(settings) as session:
        if session.scalar(select(User).where(User.username == settings.default_admin_username)) is None:
            session.add(
                User(
                    username=settings.default_admin_username,
                    password_hash=hash_password(settings.default_admin_password),
                    is_active=True,
                )
            )

        if session.scalar(select(PortPool.id).limit(1)) is None:
            for port in range(settings.ssh_port_start, settings.ssh_port_end + 1):
                session.add(PortPool(service_type="ssh", port=port, status="available"))
            for port in range(settings.vnc_port_start, settings.vnc_port_end + 1):
                session.add(PortPool(service_type="vnc", port=port, status="available"))

        AlertService(settings).ensure_default_rules(session)

    _ = (Alert, AlertRule, Device, Group, OperationLog, DeviceMetric, ScheduledTask, ScheduledTaskRun, UpdateTask, UpdateTaskDevice, UpdateTaskTemplate)
