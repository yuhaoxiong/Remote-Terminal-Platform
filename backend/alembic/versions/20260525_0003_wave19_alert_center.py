"""add alert center tables

Revision ID: 20260525_0003
Revises: 20260521_0002
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa

revision = "20260525_0003"
down_revision = "20260521_0002"
branch_labels = None
depends_on = None


DEFAULT_RULES = [
    ("device_status", True, "warning", None, None),
    ("cpu_high", True, "warning", 85.0, None),
    ("memory_high", True, "warning", 85.0, None),
    ("disk_high", True, "critical", 90.0, None),
    ("metrics_stale", True, "warning", None, 10),
    ("scheduled_task_failed", True, "critical", None, None),
    ("update_task_failed", True, "critical", None, None),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "alerts" not in table_names:
        op.create_table(
            "alerts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("dedupe_key", sa.String(length=255), nullable=False),
            sa.Column("alert_type", sa.String(length=64), nullable=False),
            sa.Column("severity", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("source_type", sa.String(length=64), nullable=False),
            sa.Column("source_id", sa.Integer(), nullable=True),
            sa.Column("device_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("first_triggered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("last_triggered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("trigger_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("acknowledged_note", sa.Text(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_by", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_alerts_dedupe_key"), "alerts", ["dedupe_key"])
        op.create_index(op.f("ix_alerts_alert_type"), "alerts", ["alert_type"])
        op.create_index(op.f("ix_alerts_severity"), "alerts", ["severity"])
        op.create_index(op.f("ix_alerts_status"), "alerts", ["status"])
        op.create_index(op.f("ix_alerts_source_type"), "alerts", ["source_type"])
        op.create_index(op.f("ix_alerts_source_id"), "alerts", ["source_id"])
        op.create_index(op.f("ix_alerts_device_id"), "alerts", ["device_id"])
        op.create_index(op.f("ix_alerts_first_triggered_at"), "alerts", ["first_triggered_at"])
        op.create_index(op.f("ix_alerts_last_triggered_at"), "alerts", ["last_triggered_at"])

    if "alert_rules" not in table_names:
        op.create_table(
            "alert_rules",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("rule_type", sa.String(length=64), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("severity", sa.String(length=32), nullable=False),
            sa.Column("threshold_value", sa.Float(), nullable=True),
            sa.Column("window_minutes", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("rule_type", name="uq_alert_rules_rule_type"),
        )
        op.create_index(op.f("ix_alert_rules_rule_type"), "alert_rules", ["rule_type"], unique=True)
        op.create_index(op.f("ix_alert_rules_enabled"), "alert_rules", ["enabled"])

    existing = {row[0] for row in bind.execute(sa.text("SELECT rule_type FROM alert_rules")).fetchall()}
    for rule_type, enabled, severity, threshold_value, window_minutes in DEFAULT_RULES:
        if rule_type in existing:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO alert_rules (rule_type, enabled, severity, threshold_value, window_minutes)
                VALUES (:rule_type, :enabled, :severity, :threshold_value, :window_minutes)
                """
            ),
            {
                "rule_type": rule_type,
                "enabled": enabled,
                "severity": severity,
                "threshold_value": threshold_value,
                "window_minutes": window_minutes,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "alert_rules" in table_names:
        op.drop_table("alert_rules")
    if "alerts" in table_names:
        op.drop_table("alerts")
