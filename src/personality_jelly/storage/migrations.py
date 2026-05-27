from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    text,
    inspect,
    select,
)
from sqlalchemy import JSON as SAJSON
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
_source_works = Table(
    "source_works",
    _metadata,
    Column("id", String(64), primary_key=True),
)
_source_chunks = Table(
    "source_chunks",
    _metadata,
    Column("id", String(96), primary_key=True),
)
_characters = Table(
    "characters",
    _metadata,
    Column("id", String(64), primary_key=True),
)
_source_chunk_embeddings = Table(
    "source_chunk_embeddings",
    _metadata,
    Column("id", String(96), primary_key=True),
    Column("source_chunk_id", String(96), ForeignKey("source_chunks.id"), nullable=False),
    Column("embedding_model", String(128), nullable=False),
    Column("embedding", SAJSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index(
        "ux_source_chunk_embeddings_chunk_model",
        "source_chunk_id",
        "embedding_model",
        unique=True,
    ),
)
_retrieval_evaluation_runs = Table(
    "retrieval_evaluation_runs",
    _metadata,
    Column("id", String(96), primary_key=True),
    Column("source_work_id", String(64), ForeignKey("source_works.id"), nullable=False),
    Column("character_id", String(64), ForeignKey("characters.id"), nullable=False),
    Column("test_suite", String(128), nullable=False),
    Column("status", String(32), nullable=False),
    Column("total_cases", Integer, nullable=False),
    Column("passed_cases", Integer, nullable=False),
    Column("failed_cases", Integer, nullable=False),
    Column("embedding_model", String(128)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    Index(
        "ix_retrieval_evaluation_runs_character_suite",
        "character_id",
        "test_suite",
    ),
)
_retrieval_evaluation_case_results = Table(
    "retrieval_evaluation_case_results",
    _metadata,
    Column("id", String(96), primary_key=True),
    Column(
        "run_id",
        String(96),
        ForeignKey("retrieval_evaluation_runs.id"),
        nullable=False,
    ),
    Column("case_id", String(128), nullable=False),
    Column("query", Text, nullable=False),
    Column("expected_chunk_ids", SAJSON, nullable=False),
    Column("retrieved_chunk_ids", SAJSON, nullable=False),
    Column("retrieved_scores", SAJSON, nullable=False),
    Column("status", String(32), nullable=False),
    Column("recall", Float, nullable=False),
    Column("first_relevant_rank", Integer),
    Column("ranking_score", Float, nullable=False),
    Column("reasons", SAJSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_retrieval_evaluation_case_results_run", "run_id"),
)
_workflow_runs = Table(
    "workflow_runs",
    _metadata,
    Column("workflow_id", String(128), primary_key=True),
    Column("request_id", String(128), nullable=False),
    Column("workflow_type", String(128), nullable=False),
    Column("status", String(32), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    Column("error_code", String(128)),
    Column("error_details", SAJSON),
    Column("failed_step", String(128)),
    Column("warnings", SAJSON, nullable=False),
    Column("persisted_ids", SAJSON, nullable=False),
    Index("ix_workflow_runs_request", "request_id"),
    Index("ix_workflow_runs_type_started", "workflow_type", "started_at"),
    Index("ix_workflow_runs_status_started", "status", "started_at"),
)
_workflow_run_links = Table(
    "workflow_run_links",
    _metadata,
    Column("id", String(96), primary_key=True),
    Column("workflow_id", String(128), ForeignKey("workflow_runs.workflow_id"), nullable=False),
    Column("entity_type", String(128), nullable=False),
    Column("entity_id", String(128), nullable=False),
    Column("relation", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_workflow_run_links_workflow", "workflow_id"),
    Index("ix_workflow_run_links_entity", "entity_type", "entity_id"),
)


def _apply_initial_schema(engine: Engine) -> None:
    orm.create_all(engine)


def _apply_source_chunk_embeddings(engine: Engine) -> None:
    _source_chunk_embeddings.create(engine, checkfirst=True)


def _apply_retrieval_evaluation(engine: Engine) -> None:
    _retrieval_evaluation_runs.create(engine, checkfirst=True)
    _retrieval_evaluation_case_results.create(engine, checkfirst=True)


def _apply_workflow_persistence(engine: Engine) -> None:
    _workflow_runs.create(engine, checkfirst=True)
    _workflow_run_links.create(engine, checkfirst=True)
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("llm_raw_outputs")}
    statements: list[str] = []
    if "request_id" not in columns:
        statements.append("ALTER TABLE llm_raw_outputs ADD COLUMN request_id VARCHAR(128)")
    if "workflow_id" not in columns:
        statements.append("ALTER TABLE llm_raw_outputs ADD COLUMN workflow_id VARCHAR(128)")
    if "workflow_step" not in columns:
        statements.append("ALTER TABLE llm_raw_outputs ADD COLUMN workflow_step VARCHAR(128)")
    if "related_ids" not in columns:
        statements.append("ALTER TABLE llm_raw_outputs ADD COLUMN related_ids JSON")
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_llm_raw_outputs_workflow "
                "ON llm_raw_outputs (workflow_id, workflow_step)"
            )
        )


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version="0001_initial_schema",
        description="Create MVP relational schema",
        apply=_apply_initial_schema,
    ),
    Migration(
        version="0002_source_chunk_embeddings",
        description="Persist source chunk embeddings",
        apply=_apply_source_chunk_embeddings,
    ),
    Migration(
        version="0003_retrieval_evaluation",
        description="Persist retrieval quality evaluation runs",
        apply=_apply_retrieval_evaluation,
    ),
    Migration(
        version="0005_workflow_persistence",
        description="Persist workflow runs, workflow links, and LLM trace correlation",
        apply=_apply_workflow_persistence,
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
