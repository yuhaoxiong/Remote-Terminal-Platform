from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.config import Settings
from app.database import get_engine


@dataclass(frozen=True)
class MigrationStatus:
    current_revision: str | None
    head_revision: str | None
    has_pending_migrations: bool
    last_error: str | None = None


def alembic_config(settings: Settings) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def upgrade_to_head(settings: Settings) -> None:
    command.upgrade(alembic_config(settings), "head")


def migration_status(settings: Settings) -> MigrationStatus:
    config = alembic_config(settings)
    script = ScriptDirectory.from_config(config)
    head_revision = script.get_current_head()
    try:
        with get_engine(settings).connect() as connection:
            context = MigrationContext.configure(connection)
            current_revision = context.get_current_revision()
    except Exception as exc:
        return MigrationStatus(
            current_revision=None,
            head_revision=head_revision,
            has_pending_migrations=True,
            last_error=str(exc),
        )
    return MigrationStatus(
        current_revision=current_revision,
        head_revision=head_revision,
        has_pending_migrations=current_revision != head_revision,
    )
