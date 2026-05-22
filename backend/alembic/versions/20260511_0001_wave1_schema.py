"""create wave 1 schema

Revision ID: 20260511_0001
Revises:
Create Date: 2026-05-11
"""

from alembic import op

from app.database import Base
from app.models.device import Device
from app.models.group import Group
from app.models.log import OperationLog
from app.models.metric import DeviceMetric
from app.models.port_pool import PortPool
from app.models.scheduled_task import ScheduledTask, ScheduledTaskRun
from app.models.update_task import UpdateTask, UpdateTaskDevice, UpdateTaskTemplate
from app.models.user import User

revision = "20260511_0001"
down_revision = None
branch_labels = None
depends_on = None

_ = (
    Device,
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


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
