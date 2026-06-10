"""add system settings

Revision ID: 20260610_0006
Revises: 20260604_0005
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa

revision = "20260610_0006"
down_revision = "20260604_0005"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def upgrade() -> None:
    tables = _table_names()
    if "system_settings" not in tables:
        op.create_table(
            "system_settings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(length=120), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=False),
            sa.Column("value_type", sa.String(length=32), nullable=False),
            sa.Column("value_json", sa.JSON(), nullable=True),
            sa.Column("secret_value_encrypted", sa.Text(), nullable=True),
            sa.Column("source", sa.String(length=32), nullable=False),
            sa.Column("is_secret", sa.Boolean(), nullable=False),
            sa.Column("requires_restart", sa.Boolean(), nullable=False),
            sa.Column("pending_restart", sa.Boolean(), nullable=False),
            sa.Column("is_valid", sa.Boolean(), nullable=False),
            sa.Column("invalid_reason", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key"),
        )
        op.create_index(op.f("ix_system_settings_key"), "system_settings", ["key"])
        op.create_index(op.f("ix_system_settings_category"), "system_settings", ["category"])
        op.create_index(op.f("ix_system_settings_source"), "system_settings", ["source"])
        op.create_index(op.f("ix_system_settings_requires_restart"), "system_settings", ["requires_restart"])
        op.create_index(op.f("ix_system_settings_pending_restart"), "system_settings", ["pending_restart"])
        op.create_index(op.f("ix_system_settings_is_valid"), "system_settings", ["is_valid"])

    if "system_setting_changes" not in tables:
        op.create_table(
            "system_setting_changes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("setting_key", sa.String(length=120), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=False),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("old_source", sa.String(length=32), nullable=True),
            sa.Column("new_source", sa.String(length=32), nullable=True),
            sa.Column("old_value_snapshot", sa.Text(), nullable=True),
            sa.Column("new_value_snapshot", sa.Text(), nullable=True),
            sa.Column("is_secret", sa.Boolean(), nullable=False),
            sa.Column("requires_restart", sa.Boolean(), nullable=False),
            sa.Column("pending_restart_after_change", sa.Boolean(), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("actor_username", sa.String(length=64), nullable=True),
            sa.Column("client_ip", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_system_setting_changes_setting_key"), "system_setting_changes", ["setting_key"])
        op.create_index(op.f("ix_system_setting_changes_category"), "system_setting_changes", ["category"])
        op.create_index(op.f("ix_system_setting_changes_action"), "system_setting_changes", ["action"])
        op.create_index(op.f("ix_system_setting_changes_created_at"), "system_setting_changes", ["created_at"])


def downgrade() -> None:
    tables = _table_names()
    if "system_setting_changes" in tables:
        op.drop_index(op.f("ix_system_setting_changes_created_at"), table_name="system_setting_changes")
        op.drop_index(op.f("ix_system_setting_changes_action"), table_name="system_setting_changes")
        op.drop_index(op.f("ix_system_setting_changes_category"), table_name="system_setting_changes")
        op.drop_index(op.f("ix_system_setting_changes_setting_key"), table_name="system_setting_changes")
        op.drop_table("system_setting_changes")
    if "system_settings" in tables:
        op.drop_index(op.f("ix_system_settings_is_valid"), table_name="system_settings")
        op.drop_index(op.f("ix_system_settings_pending_restart"), table_name="system_settings")
        op.drop_index(op.f("ix_system_settings_requires_restart"), table_name="system_settings")
        op.drop_index(op.f("ix_system_settings_source"), table_name="system_settings")
        op.drop_index(op.f("ix_system_settings_category"), table_name="system_settings")
        op.drop_index(op.f("ix_system_settings_key"), table_name="system_settings")
        op.drop_table("system_settings")
