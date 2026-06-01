"""add alert notification tables

Revision ID: 20260601_0004
Revises: 20260525_0003
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa

revision = "20260601_0004"
down_revision = "20260525_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "alert_notification_channels" not in table_names:
        op.create_table(
            "alert_notification_channels",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("channel_type", sa.String(length=32), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("config", sa.JSON(), nullable=False),
            sa.Column("secret_config_encrypted", sa.Text(), nullable=True),
            sa.Column("last_test_status", sa.String(length=32), nullable=True),
            sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_alert_notification_channels_channel_type"), "alert_notification_channels", ["channel_type"])
        op.create_index(op.f("ix_alert_notification_channels_enabled"), "alert_notification_channels", ["enabled"])

    if "alert_notification_policies" not in table_names:
        op.create_table(
            "alert_notification_policies",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("channel_id", sa.Integer(), nullable=False),
            sa.Column("min_severity", sa.String(length=32), nullable=False),
            sa.Column("source_types", sa.JSON(), nullable=False),
            sa.Column("alert_statuses", sa.JSON(), nullable=False),
            sa.Column("event_types", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["channel_id"], ["alert_notification_channels.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_alert_notification_policies_channel_id"), "alert_notification_policies", ["channel_id"])
        op.create_index(op.f("ix_alert_notification_policies_enabled"), "alert_notification_policies", ["enabled"])

    if "alert_notification_deliveries" not in table_names:
        op.create_table(
            "alert_notification_deliveries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("alert_id", sa.Integer(), nullable=False),
            sa.Column("channel_id", sa.Integer(), nullable=False),
            sa.Column("policy_id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False),
            sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("response_status_code", sa.Integer(), nullable=True),
            sa.Column("response_summary", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"]),
            sa.ForeignKeyConstraint(["channel_id"], ["alert_notification_channels.id"]),
            sa.ForeignKeyConstraint(["policy_id"], ["alert_notification_policies.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("alert_id", "channel_id", "policy_id", "event_type", name="uq_alert_notification_delivery_event"),
        )
        op.create_index(op.f("ix_alert_notification_deliveries_alert_id"), "alert_notification_deliveries", ["alert_id"])
        op.create_index(op.f("ix_alert_notification_deliveries_channel_id"), "alert_notification_deliveries", ["channel_id"])
        op.create_index(op.f("ix_alert_notification_deliveries_policy_id"), "alert_notification_deliveries", ["policy_id"])
        op.create_index(op.f("ix_alert_notification_deliveries_event_type"), "alert_notification_deliveries", ["event_type"])
        op.create_index(op.f("ix_alert_notification_deliveries_status"), "alert_notification_deliveries", ["status"])
        op.create_index(op.f("ix_alert_notification_deliveries_next_retry_at"), "alert_notification_deliveries", ["next_retry_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "alert_notification_deliveries" in table_names:
        op.drop_index(op.f("ix_alert_notification_deliveries_next_retry_at"), table_name="alert_notification_deliveries")
        op.drop_index(op.f("ix_alert_notification_deliveries_status"), table_name="alert_notification_deliveries")
        op.drop_index(op.f("ix_alert_notification_deliveries_event_type"), table_name="alert_notification_deliveries")
        op.drop_index(op.f("ix_alert_notification_deliveries_policy_id"), table_name="alert_notification_deliveries")
        op.drop_index(op.f("ix_alert_notification_deliveries_channel_id"), table_name="alert_notification_deliveries")
        op.drop_index(op.f("ix_alert_notification_deliveries_alert_id"), table_name="alert_notification_deliveries")
        op.drop_table("alert_notification_deliveries")
    if "alert_notification_policies" in table_names:
        op.drop_index(op.f("ix_alert_notification_policies_enabled"), table_name="alert_notification_policies")
        op.drop_index(op.f("ix_alert_notification_policies_channel_id"), table_name="alert_notification_policies")
        op.drop_table("alert_notification_policies")
    if "alert_notification_channels" in table_names:
        op.drop_index(op.f("ix_alert_notification_channels_enabled"), table_name="alert_notification_channels")
        op.drop_index(op.f("ix_alert_notification_channels_channel_type"), table_name="alert_notification_channels")
        op.drop_table("alert_notification_channels")
