from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, MetaData, String, Table, inspect, select
from sqlalchemy.engine import Engine

from personality_jelly.storage import orm


SCHEMA_MIGRATIONS_TABLE = "schema_migrations"


@dataclass(frozen=True)
class Migration:
    version: str
    description: str
    apply: Callable[[Engine], None]


@dataclass(frozen=True)
class AppliedMigration:
    version: str
    description: str
    applied_at: datetime


@dataclass(frozen=True)
class MigrationStatus:
    current_version: str | None
    target_version: str
    applied: tuple[AppliedMigration, ...]
    pending: tuple[Migration, ...]
    has_schema_migrations_table: bool
    has_application_tables: bool


@dataclass(frozen=True)
class MigrationResult:
    applied: tuple[AppliedMigration, ...]
    status: MigrationStatus
    baselined_existing_database: bool = False


_metadata = MetaData()
_schema_migrations = Table(
    SCHEMA_MIGRATIONS_TABLE,
    _metadata,
    Column("version", String(64), primary_key=True),
    Column("description", String(255), nullable=False),
    Column("applied_at", DateTime(timezone=True), nullable=False),
)


def _apply_initial_schema(engine: Engine) -> None:
    orm.create_all(engine)


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version="0001_initial_schema",
        description="Create MVP relational schema",
        apply=_apply_initial_schema,
    ),
)

CURRENT_SCHEMA_VERSION = MIGRATIONS[-1].version


def get_migration_status(engine: Engine) -> MigrationStatus:
    table_names = set(inspect(engine).get_table_names())
    has_migration_table = SCHEMA_MIGRATIONS_TABLE in table_names
    applied = _list_applied_migrations(engine) if has_migration_table else ()
    applied_versions = {migration.version for migration in applied}
    pending = tuple(
        migration for migration in MIGRATIONS if migration.version not in applied_versions
    )
    current_version = applied[-1].version if applied else None
    return MigrationStatus(
        current_version=current_version,
        target_version=CURRENT_SCHEMA_VERSION,
        applied=applied,
        pending=pending,
        has_schema_migrations_table=has_migration_table,
        has_application_tables=_has_application_tables(table_names),
    )


def migrate_database(engine: Engine) -> MigrationResult:
    initial_status = get_migration_status(engine)
    _ensure_schema_migrations_table(engine)
    applied: list[AppliedMigration] = []
    baselined = (
        initial_status.has_application_tables
        and not initial_status.has_schema_migrations_table
    )

    for migration in initial_status.pending:
        migration.apply(engine)
        applied.append(_record_migration(engine, migration))

    return MigrationResult(
        applied=tuple(applied),
        status=get_migration_status(engine),
        baselined_existing_database=baselined,
    )


def ensure_database_ready(engine: Engine) -> MigrationStatus:
    return migrate_database(engine).status


def _ensure_schema_migrations_table(engine: Engine) -> None:
    _schema_migrations.create(engine, checkfirst=True)


def _record_migration(engine: Engine, migration: Migration) -> AppliedMigration:
    applied_at = datetime.now(timezone.utc)
    record = AppliedMigration(
        version=migration.version,
        description=migration.description,
        applied_at=applied_at,
    )
    with engine.begin() as connection:
        connection.execute(
            _schema_migrations.insert().values(
                version=record.version,
                description=record.description,
                applied_at=record.applied_at,
            )
        )
    return record


def _list_applied_migrations(engine: Engine) -> tuple[AppliedMigration, ...]:
    statement = select(_schema_migrations).order_by(_schema_migrations.c.version.asc())
    with engine.connect() as connection:
        rows = connection.execute(statement).mappings().all()
    return tuple(
        AppliedMigration(
            version=row["version"],
            description=row["description"],
            applied_at=row["applied_at"],
        )
        for row in rows
    )


def _has_application_tables(table_names: set[str]) -> bool:
    return any(table_name != SCHEMA_MIGRATIONS_TABLE for table_name in table_names)
