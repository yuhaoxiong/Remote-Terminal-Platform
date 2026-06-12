from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.database import Base
from app.models.alert import Alert, AlertRule
from app.models.alert_notification import AlertNotificationChannel, AlertNotificationDelivery, AlertNotificationPolicy
from app.models.device import Device
from app.models.group import Group
from app.models.log import OperationLog
from app.models.metric import DeviceMetric
from app.models.port_pool import PortPool
from app.models.scheduled_task import ScheduledTask, ScheduledTaskRun
from app.models.update_task import UpdateTask, UpdateTaskDevice, UpdateTaskTemplate
from app.models.user import User

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
_ = (
    Device,
    Alert,
    AlertRule,
    AlertNotificationChannel,
    AlertNotificationDelivery,
    AlertNotificationPolicy,
    Group,
    OperationLog,
    DeviceMetric,
    PortPool,
    ScheduledTask,
    ScheduledTaskRun,
    UpdateTask,
    UpdateTaskDevice,
    UpdateTaskTemplate,
    User,
)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # sqlite 相对路径(如 CI、全新部署、克隆)下父目录可能不存在,
    # alembic 自建 engine 绕过了 database.py 的建目录保护,故在此补齐。
    url = config.get_main_option("sqlalchemy.url")
    if url and url.startswith("sqlite:///"):
        db_path = Path(url.replace("sqlite:///", "", 1))
        db_path.parent.mkdir(parents=True, exist_ok=True)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
