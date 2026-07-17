"""add edge function lifecycle domain

Revision ID: 20260717_0007
Revises: 20260610_0006
Create Date: 2026-07-17
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "20260717_0007"
down_revision = "20260610_0006"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    tables = _table_names()

    if "projects" not in tables:
        op.create_table(
            "projects",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
        op.create_index(op.f("ix_projects_code"), "projects", ["code"])
        op.create_index(op.f("ix_projects_name"), "projects", ["name"])
        op.create_index(op.f("ix_projects_status"), "projects", ["status"])

    if "hardware_profiles" not in tables:
        op.create_table(
            "hardware_profiles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("soc", sa.String(length=32), nullable=False),
            sa.Column("memory_mb", sa.Integer(), nullable=False),
            sa.Column("os_version", sa.String(length=64), nullable=False),
            sa.Column("rknn_version", sa.String(length=64), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
        op.create_index(op.f("ix_hardware_profiles_code"), "hardware_profiles", ["code"])
        op.create_index(op.f("ix_hardware_profiles_soc"), "hardware_profiles", ["soc"])
        op.create_index(op.f("ix_hardware_profiles_os_version"), "hardware_profiles", ["os_version"])
        op.create_index(op.f("ix_hardware_profiles_active"), "hardware_profiles", ["active"])

    if "devices" in tables and "device_uuid" not in {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("devices")
    }:
        indexes = _index_names("devices")
        if "ix_devices_project_id" in indexes:
            op.drop_index("ix_devices_project_id", table_name="devices")
        with op.batch_alter_table(
            "devices",
            recreate="always",
            partial_reordering=[
                (
                    "id",
                    "device_uuid",
                    "name",
                    "device_sn",
                    "project_ref_id",
                    "expected_profile_id",
                    "actual_profile_id",
                    "device_role",
                    "is_test_device",
                    "location",
                    "hardware_model",
                    "ssh_port",
                    "vnc_port",
                    "ssh_user",
                    "ssh_auth_type",
                    "ssh_password_encrypted",
                    "ssh_key_encrypted",
                    "local_ip",
                    "os_version",
                    "description",
                    "tags",
                    "group_id",
                    "status",
                    "last_seen",
                    "created_at",
                    "updated_at",
                )
            ],
        ) as batch_op:
            batch_op.drop_column("project_id")
            batch_op.add_column(sa.Column("device_uuid", sa.String(length=36), nullable=True))
            batch_op.add_column(sa.Column("project_ref_id", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("expected_profile_id", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("actual_profile_id", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("device_role", sa.String(length=64), nullable=True))
            batch_op.add_column(
                sa.Column("is_test_device", sa.Boolean(), nullable=False, server_default=sa.false())
            )
            batch_op.create_foreign_key(
                "fk_devices_project_id",
                "projects",
                ["project_ref_id"],
                ["id"],
            )
            batch_op.create_foreign_key(
                "fk_devices_expected_profile_id",
                "hardware_profiles",
                ["expected_profile_id"],
                ["id"],
            )
            batch_op.create_foreign_key(
                "fk_devices_actual_profile_id",
                "hardware_profiles",
                ["actual_profile_id"],
                ["id"],
            )

        op.alter_column("devices", "project_ref_id", new_column_name="project_id")

        devices = sa.table("devices", sa.column("id", sa.Integer()), sa.column("device_uuid", sa.String()))
        bind = op.get_bind()
        device_ids = list(bind.execute(sa.select(devices.c.id)).scalars())
        for device_id in device_ids:
            bind.execute(
                devices.update().where(devices.c.id == device_id).values(device_uuid=str(uuid4()))
            )

        indexes = _index_names("devices")
        for index_name, columns, unique in (
            ("ix_devices_device_uuid", ["device_uuid"], True),
            ("ix_devices_project_id", ["project_id"], False),
            ("ix_devices_expected_profile_id", ["expected_profile_id"], False),
            ("ix_devices_actual_profile_id", ["actual_profile_id"], False),
            ("ix_devices_is_test_device", ["is_test_device"], False),
        ):
            if index_name not in indexes:
                op.create_index(index_name, "devices", columns, unique=unique)

    if "functions" not in tables:
        op.create_table(
            "functions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
        op.create_index(op.f("ix_functions_code"), "functions", ["code"])
        op.create_index(op.f("ix_functions_name"), "functions", ["name"])
        op.create_index(op.f("ix_functions_status"), "functions", ["status"])

    if "function_releases" not in tables:
        op.create_table(
            "function_releases",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("function_id", sa.Integer(), nullable=False),
            sa.Column("version", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("manifest_json", sa.JSON(), nullable=True),
            sa.Column("release_notes", sa.Text(), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["function_id"], ["functions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("function_id", "version", name="uq_function_release_version"),
        )
        op.create_index(op.f("ix_function_releases_function_id"), "function_releases", ["function_id"])
        op.create_index(op.f("ix_function_releases_version"), "function_releases", ["version"])
        op.create_index(op.f("ix_function_releases_status"), "function_releases", ["status"])

    if "function_variants" not in tables:
        op.create_table(
            "function_variants",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("release_id", sa.Integer(), nullable=False),
            sa.Column("hardware_profile_id", sa.Integer(), nullable=False),
            sa.Column("artifact_uri", sa.String(length=500), nullable=False),
            sa.Column("artifact_sha256", sa.String(length=64), nullable=False),
            sa.Column("artifact_size", sa.BigInteger(), nullable=False),
            sa.Column("signature", sa.Text(), nullable=True),
            sa.Column("key_id", sa.String(length=120), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["hardware_profile_id"], ["hardware_profiles.id"]),
            sa.ForeignKeyConstraint(["release_id"], ["function_releases.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("release_id", "hardware_profile_id", name="uq_release_hardware_variant"),
        )
        op.create_index(op.f("ix_function_variants_release_id"), "function_variants", ["release_id"])
        op.create_index(op.f("ix_function_variants_hardware_profile_id"), "function_variants", ["hardware_profile_id"])
        op.create_index(op.f("ix_function_variants_artifact_sha256"), "function_variants", ["artifact_sha256"])
        op.create_index(op.f("ix_function_variants_status"), "function_variants", ["status"])

    if "project_functions" not in tables:
        op.create_table(
            "project_functions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("function_id", sa.Integer(), nullable=False),
            sa.Column("desired_release_id", sa.Integer(), nullable=False),
            sa.Column("config_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["desired_release_id"], ["function_releases.id"]),
            sa.ForeignKeyConstraint(["function_id"], ["functions.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "function_id", name="uq_project_function"),
        )
        op.create_index(op.f("ix_project_functions_project_id"), "project_functions", ["project_id"])
        op.create_index(op.f("ix_project_functions_function_id"), "project_functions", ["function_id"])
        op.create_index(op.f("ix_project_functions_desired_release_id"), "project_functions", ["desired_release_id"])
        op.create_index(op.f("ix_project_functions_status"), "project_functions", ["status"])

    if "device_release_overrides" not in tables:
        op.create_table(
            "device_release_overrides",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("device_id", sa.Integer(), nullable=False),
            sa.Column("function_id", sa.Integer(), nullable=False),
            sa.Column("release_id", sa.Integer(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
            sa.ForeignKeyConstraint(["function_id"], ["functions.id"]),
            sa.ForeignKeyConstraint(["release_id"], ["function_releases.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("device_id", "function_id", name="uq_device_function_override"),
        )
        op.create_index(op.f("ix_device_release_overrides_device_id"), "device_release_overrides", ["device_id"])
        op.create_index(op.f("ix_device_release_overrides_function_id"), "device_release_overrides", ["function_id"])
        op.create_index(op.f("ix_device_release_overrides_release_id"), "device_release_overrides", ["release_id"])
        op.create_index(op.f("ix_device_release_overrides_expires_at"), "device_release_overrides", ["expires_at"])
        op.create_index(op.f("ix_device_release_overrides_active"), "device_release_overrides", ["active"])

    if "deployment_plans" not in tables:
        op.create_table(
            "deployment_plans",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("stale_reason", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("confirmed_by", sa.Integer(), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_deployment_plans_project_id"), "deployment_plans", ["project_id"])
        op.create_index(op.f("ix_deployment_plans_status"), "deployment_plans", ["status"])
        op.create_index(op.f("ix_deployment_plans_snapshot_hash"), "deployment_plans", ["snapshot_hash"])
        op.create_index(op.f("ix_deployment_plans_expires_at"), "deployment_plans", ["expires_at"])

    if "deployment_plan_items" not in tables:
        op.create_table(
            "deployment_plan_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("device_id", sa.Integer(), nullable=False),
            sa.Column("function_id", sa.Integer(), nullable=False),
            sa.Column("release_id", sa.Integer(), nullable=False),
            sa.Column("variant_id", sa.Integer(), nullable=False),
            sa.Column("config_snapshot", sa.JSON(), nullable=True),
            sa.Column("config_hash", sa.String(length=64), nullable=False),
            sa.Column("artifact_sha256", sa.String(length=64), nullable=False),
            sa.Column("preflight_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
            sa.ForeignKeyConstraint(["function_id"], ["functions.id"]),
            sa.ForeignKeyConstraint(["plan_id"], ["deployment_plans.id"]),
            sa.ForeignKeyConstraint(["release_id"], ["function_releases.id"]),
            sa.ForeignKeyConstraint(["variant_id"], ["function_variants.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("plan_id", "device_id", "function_id", name="uq_plan_device_function"),
        )
        for column in ("plan_id", "device_id", "function_id", "release_id", "variant_id", "status"):
            op.create_index(op.f(f"ix_deployment_plan_items_{column}"), "deployment_plan_items", [column])

    if "deployment_executions" not in tables:
        op.create_table(
            "deployment_executions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("execution_id", sa.String(length=36), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["plan_id"], ["deployment_plans.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("execution_id"),
            sa.UniqueConstraint("plan_id"),
        )
        op.create_index(op.f("ix_deployment_executions_execution_id"), "deployment_executions", ["execution_id"], unique=True)
        op.create_index(op.f("ix_deployment_executions_plan_id"), "deployment_executions", ["plan_id"], unique=True)
        op.create_index(op.f("ix_deployment_executions_status"), "deployment_executions", ["status"])

    if "deployment_execution_items" not in tables:
        op.create_table(
            "deployment_execution_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("deployment_execution_id", sa.Integer(), nullable=False),
            sa.Column("plan_item_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["deployment_execution_id"], ["deployment_executions.id"]),
            sa.ForeignKeyConstraint(["plan_item_id"], ["deployment_plan_items.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("deployment_execution_id", "plan_item_id", name="uq_execution_plan_item"),
        )
        op.create_index(
            op.f("ix_deployment_execution_items_deployment_execution_id"),
            "deployment_execution_items",
            ["deployment_execution_id"],
        )
        op.create_index(op.f("ix_deployment_execution_items_plan_item_id"), "deployment_execution_items", ["plan_item_id"])
        op.create_index(op.f("ix_deployment_execution_items_status"), "deployment_execution_items", ["status"])

    profiles = sa.table(
        "hardware_profiles",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("soc", sa.String()),
        sa.column("memory_mb", sa.Integer()),
        sa.column("os_version", sa.String()),
        sa.column("rknn_version", sa.String()),
        sa.column("active", sa.Boolean()),
    )
    bind = op.get_bind()
    existing_profile_codes = set(bind.execute(sa.select(profiles.c.code)).scalars())
    profile_rows = [
        {
            "code": "rk3568-4g-debian11",
            "name": "RK3568 4G / Debian 11",
            "soc": "rk3568",
            "memory_mb": 4096,
            "os_version": "debian11",
            "rknn_version": None,
            "active": True,
        },
        {
            "code": "rk3588-8g-debian11",
            "name": "RK3588 8G / Debian 11",
            "soc": "rk3588",
            "memory_mb": 8192,
            "os_version": "debian11",
            "rknn_version": None,
            "active": True,
        },
    ]
    for row in profile_rows:
        if row["code"] not in existing_profile_codes:
            bind.execute(profiles.insert().values(**row))


def downgrade() -> None:
    tables = _table_names()
    for table_name in (
        "deployment_execution_items",
        "deployment_executions",
        "deployment_plan_items",
        "deployment_plans",
        "device_release_overrides",
        "project_functions",
        "function_variants",
        "function_releases",
        "functions",
    ):
        if table_name in tables:
            op.drop_table(table_name)

    if "devices" in tables:
        for index_name in (
            "ix_devices_device_uuid",
            "ix_devices_project_id",
            "ix_devices_expected_profile_id",
            "ix_devices_actual_profile_id",
            "ix_devices_is_test_device",
        ):
            if index_name in _index_names("devices"):
                op.drop_index(index_name, table_name="devices")
        with op.batch_alter_table(
            "devices",
            recreate="always",
            partial_reordering=[
                (
                    "id",
                    "name",
                    "device_sn",
                    "legacy_project_id",
                    "location",
                    "hardware_model",
                    "ssh_port",
                    "vnc_port",
                    "ssh_user",
                    "ssh_auth_type",
                    "ssh_password_encrypted",
                    "ssh_key_encrypted",
                    "local_ip",
                    "os_version",
                    "description",
                    "tags",
                    "group_id",
                    "status",
                    "last_seen",
                    "created_at",
                    "updated_at",
                )
            ],
        ) as batch_op:
            batch_op.drop_column("device_uuid")
            batch_op.drop_column("project_id")
            batch_op.drop_column("expected_profile_id")
            batch_op.drop_column("actual_profile_id")
            batch_op.drop_column("device_role")
            batch_op.drop_column("is_test_device")
            batch_op.add_column(
                sa.Column("legacy_project_id", sa.String(length=120), nullable=False, server_default="")
            )
        op.alter_column("devices", "legacy_project_id", new_column_name="project_id")
        op.create_index(op.f("ix_devices_project_id"), "devices", ["project_id"])

    if "hardware_profiles" in tables:
        op.drop_table("hardware_profiles")
    if "projects" in tables:
        op.drop_table("projects")
