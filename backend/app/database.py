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
    if "update_tasks" not in table_names:
        return

    update_task_columns = {column["name"] for column in inspector.get_columns("update_tasks")}
    with engine.begin() as connection:
        if "failure_strategy" not in update_task_columns:
            connection.execute(
                text("ALTER TABLE update_tasks ADD COLUMN failure_strategy VARCHAR(32) NOT NULL DEFAULT 'continue'")
            )
        if "concurrency_limit" not in update_task_columns:
            connection.execute(text("ALTER TABLE update_tasks ADD COLUMN concurrency_limit INTEGER NOT NULL DEFAULT 5"))


def init_db(settings: Settings | None = None) -> None:
    from app.models.device import Device
    from app.models.group import Group
    from app.models.log import OperationLog
    from app.models.metric import DeviceMetric
    from app.models.port_pool import PortPool
    from app.models.scheduled_task import ScheduledTask
    from app.models.update_task import UpdateTask, UpdateTaskDevice
    from app.models.user import User
    from app.services.security import hash_password

    settings = settings or get_settings()
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

    _ = (Device, Group, OperationLog, DeviceMetric, ScheduledTask, UpdateTask, UpdateTaskDevice)
