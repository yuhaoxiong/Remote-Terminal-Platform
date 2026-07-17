"""add device bootstrap package lifecycle

Revision ID: 20260717_0008
Revises: 20260717_0007
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa

revision = "20260717_0008"
down_revision = "20260717_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("devices")}
    with op.batch_alter_table("devices") as batch_op:
        if "initialization_status" not in columns:
            batch_op.add_column(sa.Column("initialization_status", sa.String(length=32), nullable=False, server_default="draft"))
        if "vnc_status" not in columns:
            batch_op.add_column(sa.Column("vnc_status", sa.String(length=32), nullable=False, server_default="unconfigured"))
        if "bootstrap_generation" not in columns:
            batch_op.add_column(sa.Column("bootstrap_generation", sa.Integer(), nullable=False, server_default="1"))
        if "machine_id_hash" not in columns:
            batch_op.add_column(sa.Column("machine_id_hash", sa.String(length=64), nullable=True))
        if "mac_fingerprint_hash" not in columns:
            batch_op.add_column(sa.Column("mac_fingerprint_hash", sa.String(length=64), nullable=True))
        if "initialized_at" not in columns:
            batch_op.add_column(sa.Column("initialized_at", sa.DateTime(timezone=True), nullable=True))
        if "vnc_password_encrypted" not in columns:
            batch_op.add_column(sa.Column("vnc_password_encrypted", sa.Text(), nullable=True))

    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("devices")}
    for name, column in (
        ("ix_devices_initialization_status", "initialization_status"),
        ("ix_devices_vnc_status", "vnc_status"),
    ):
        if name not in indexes:
            op.create_index(name, "devices", [column])

    if "device_bootstrap_packages" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "device_bootstrap_packages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("device_id", sa.Integer(), nullable=False),
            sa.Column("generation", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("validation_errors", sa.JSON(), nullable=True),
            sa.Column("config_hash", sa.String(length=64), nullable=True),
            sa.Column("token_digest", sa.String(length=64), nullable=True),
            sa.Column("token_encrypted", sa.Text(), nullable=True),
            sa.Column("vnc_password_encrypted", sa.Text(), nullable=True),
            sa.Column("ca_sha256", sa.String(length=64), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("device_id", "generation", name="uq_device_bootstrap_generation"),
            sa.UniqueConstraint("token_digest"),
        )
        op.create_index("ix_device_bootstrap_packages_device_id", "device_bootstrap_packages", ["device_id"])
        op.create_index("ix_device_bootstrap_packages_status", "device_bootstrap_packages", ["status"])
        op.create_index("ix_device_bootstrap_packages_config_hash", "device_bootstrap_packages", ["config_hash"])
        op.create_index("ix_device_bootstrap_packages_token_digest", "device_bootstrap_packages", ["token_digest"], unique=True)

    packages = sa.table(
        "device_bootstrap_packages",
        sa.column("device_id", sa.Integer()),
        sa.column("generation", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("validation_errors", sa.JSON()),
    )
    devices = sa.table("devices", sa.column("id", sa.Integer()))
    bind = op.get_bind()
    existing = set(bind.execute(sa.select(packages.c.device_id)).scalars())
    for device_id in bind.execute(sa.select(devices.c.id)).scalars():
        if device_id not in existing:
            bind.execute(
                packages.insert().values(
                    device_id=device_id,
                    generation=1,
                    status="draft",
                    validation_errors=["尚未生成初始化包"],
                )
            )


def downgrade() -> None:
    if "device_bootstrap_packages" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("device_bootstrap_packages")
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("devices")}
    for name in ("ix_devices_initialization_status", "ix_devices_vnc_status"):
        if name in indexes:
            op.drop_index(name, table_name="devices")
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("devices")}
    with op.batch_alter_table("devices") as batch_op:
        for column in (
            "initialization_status",
            "vnc_status",
            "bootstrap_generation",
            "machine_id_hash",
            "mac_fingerprint_hash",
            "initialized_at",
            "vnc_password_encrypted",
        ):
            if column in columns:
                batch_op.drop_column(column)
