"""add user roles and audit fields

Revision ID: 20260604_0005
Revises: 20260601_0004
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa

revision = "20260604_0005"
down_revision = "20260601_0004"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names("users")
    if not columns:
        return

    if "role" not in columns:
        op.add_column("users", sa.Column("role", sa.String(length=32), nullable=False, server_default="operator"))
        op.create_index(op.f("ix_users_role"), "users", ["role"])
    if "is_active" not in columns:
        op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    if "last_login_at" not in columns:
        op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    if "last_login_ip" not in columns:
        op.add_column("users", sa.Column("last_login_ip", sa.String(length=64), nullable=True))
    if "password_changed_at" not in columns:
        op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))

    bind = op.get_bind()
    bind.execute(sa.text("UPDATE users SET role = 'admin' WHERE username = 'admin'"))
    bind.execute(sa.text("UPDATE users SET role = 'operator' WHERE role IS NULL OR role = ''"))


def downgrade() -> None:
    columns = _column_names("users")
    if "password_changed_at" in columns:
        op.drop_column("users", "password_changed_at")
    if "last_login_ip" in columns:
        op.drop_column("users", "last_login_ip")
    if "last_login_at" in columns:
        op.drop_column("users", "last_login_at")
    if "role" in columns:
        op.drop_index(op.f("ix_users_role"), table_name="users")
        op.drop_column("users", "role")
