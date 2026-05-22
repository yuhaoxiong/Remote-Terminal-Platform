"""add scheduled task run tracking

Revision ID: 20260521_0002
Revises: 20260511_0001
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa

revision = "20260521_0002"
down_revision = "20260511_0001"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "scheduled_tasks" in table_names:
        _add_column_if_missing(
            "scheduled_tasks",
            sa.Column("execution_mode", sa.String(length=32), nullable=False, server_default="dry_run"),
        )
        _add_column_if_missing(
            "scheduled_tasks",
            sa.Column("failure_strategy", sa.String(length=32), nullable=False, server_default="continue"),
        )
        _add_column_if_missing(
            "scheduled_tasks",
            sa.Column("concurrency_limit", sa.Integer(), nullable=False, server_default="5"),
        )
        _add_column_if_missing("scheduled_tasks", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing("scheduled_tasks", sa.Column("last_status", sa.String(length=32), nullable=True))
        _add_column_if_missing("scheduled_tasks", sa.Column("last_error", sa.Text(), nullable=True))
        _add_column_if_missing("scheduled_tasks", sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing(
            "scheduled_tasks",
            sa.Column("running", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )

    if "scheduled_task_runs" not in table_names:
        op.create_table(
            "scheduled_task_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("scheduled_task_id", sa.Integer(), nullable=False),
            sa.Column("trigger_type", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("output_summary", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_update_task_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["created_update_task_id"], ["update_tasks.id"]),
            sa.ForeignKeyConstraint(["scheduled_task_id"], ["scheduled_tasks.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_scheduled_task_runs_scheduled_task_id"), "scheduled_task_runs", ["scheduled_task_id"])
        op.create_index(op.f("ix_scheduled_task_runs_trigger_type"), "scheduled_task_runs", ["trigger_type"])
        op.create_index(op.f("ix_scheduled_task_runs_status"), "scheduled_task_runs", ["status"])
        op.create_index(op.f("ix_scheduled_task_runs_created_update_task_id"), "scheduled_task_runs", ["created_update_task_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "scheduled_task_runs" in table_names:
        op.drop_table("scheduled_task_runs")
