from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from personality_jelly.characters import create_character
from personality_jelly.core import Settings
from personality_jelly.domain import (
    Character,
    ClaimStatus,
    ClaimType,
    Conversation,
    InteractionMode,
    MemoryScope,
    MemoryStatus,
    PersonaVersion,
    SourceWork,
    User,
)
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.evaluation import run_ooc_benchmark, run_retrieval_benchmark
from personality_jelly.ingestion import SourceIngestionResult, ingest_text_file
from personality_jelly.llm import (
    EmbeddingConfig,
    LLMProvider,
    ModelConfig,
    build_embedding_provider,
    build_llm_provider,
)
from personality_jelly.runtime import (
    RoleplayTurnModelConfigs,
    RoleplayTurnProviders,
    create_conversation,
    create_user,
    send_roleplay_turn,
    summarize_conversation,
)
from personality_jelly.persona import compile_persona_version
from personality_jelly.storage import (
    create_database_engine,
    create_session_factory,
    ensure_database_ready,
    get_migration_status,
    migrate_database,
)
from personality_jelly.storage.repositories import (
    CharacterRepository,
    CanonClaimRepository,
    ConversationRepository,
    ContextPackageRepository,
    CriticReportRepository,
    EvaluationCaseResultRepository,
    EvaluationRunRepository,
    EvidenceRefRepository,
    FailureCaseRepository,
    LLMRawOutputRepository,
    MemoryRepository,
    MessageRepository,
    PersonaVersionRepository,
    RetrievalEvaluationCaseResultRepository,
    RetrievalEvaluationRunRepository,
    SourceWorkRepository,
    UserRepository,
)
from personality_jelly.testing.stub_provider import StubProvider


class CliError(Exception):
    """User-facing CLI error."""


@dataclass(frozen=True)
class DemoPersonaContext:
    source_work: SourceWork
    character: Character
    persona_version: PersonaVersion


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            return _run_demo(args)
        if args.command == "turn":
            return _run_turn(args)
        if args.command == "list":
            return _run_list(args)
        if args.command == "show":
            return _run_show(args)
        if args.command == "eval":
            return _run_eval(args)
        if args.command == "archive":
            return _run_archive(args)
        if args.command == "edit":
            return _run_edit(args)
        if args.command == "review":
            return _run_review(args)
        if args.command == "summarize":
            return _run_summarize(args)
        if args.command == "db":
            return _run_db(args)
        if args.command == "config":
            return _run_config(args)
        parser.print_help()
        return 1
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pjelly")
    subparsers = parser.add_subparsers(dest="command")

    demo = subparsers.add_parser("demo", help="Run a local end-to-end demo.")
    demo.add_argument("source", type=Path, help="TXT or Markdown source file.")
    demo.add_argument("--character", required=True, help="Target character name.")
    demo.add_argument("--alias", action="append", default=[], help="Character alias; may repeat.")
    demo.add_argument("--user-message", default="请记住，我喜欢在夜里写作。")
    demo.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    demo.add_argument(
        "--memory-db",
        action="store_true",
        help="Use an in-memory SQLite database for an isolated one-shot run.",
    )
    demo.add_argument(
        "--reuse-existing",
        action="store_true",
        help=(
            "Reuse matching source, character, persona, user, and conversation rows "
            "when present."
        ),
    )
    demo.add_argument("--user", default="demo-user", help="Display name for the demo user.")
    demo.add_argument(
        "--interaction-mode",
        choices=[mode.value for mode in InteractionMode],
        default=None,
        help="Optional interaction mode override. Defaults to automatic classification.",
    )
    demo.add_argument(
        "--provider",
        choices=("stub", "env"),
        default="stub",
        help="LLM provider source: stub for deterministic local output, env for PJ_* settings.",
    )
    demo.add_argument(
        "--retry-on-critic",
        action="store_true",
        help="Retry once when Critic suggests retry.",
    )

    turn = subparsers.add_parser("turn", help="Send one message to an existing conversation.")
    turn.add_argument("conversation_id", help="Existing conversation id.")
    turn.add_argument("--message", required=True, help="User message content.")
    turn.add_argument(
        "--interaction-mode",
        choices=[mode.value for mode in InteractionMode],
        default=None,
        help="Optional interaction mode override. Defaults to automatic classification.",
    )
    turn.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    turn.add_argument(
        "--provider",
        choices=("stub", "env"),
        default="stub",
        help="LLM provider source: stub for deterministic local output, env for PJ_* settings.",
    )
    turn.add_argument(
        "--retry-on-critic",
        action="store_true",
        help="Retry once when Critic suggests retry.",
    )

    list_parser = subparsers.add_parser("list", help="List persisted resources.")
    list_subparsers = list_parser.add_subparsers(dest="resource")
    list_conversations = list_subparsers.add_parser(
        "conversations",
        help="List recent conversations.",
    )
    list_conversations.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    list_conversations.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of conversations to print.",
    )
    list_memories = list_subparsers.add_parser(
        "memories",
        help="List memories for a user and character.",
    )
    list_memories.add_argument("--user-id", required=True, help="User id.")
    list_memories.add_argument("--character-id", required=True, help="Character id.")
    list_memories.add_argument(
        "--scope",
        choices=[scope.value for scope in MemoryScope],
        default=None,
        help="Optional memory scope filter.",
    )
    list_memories.add_argument(
        "--status",
        choices=[status.value for status in MemoryStatus],
        default=MemoryStatus.ACCEPTED.value,
        help="Optional memory status filter. Defaults to accepted.",
    )
    list_memories.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    list_claims = list_subparsers.add_parser(
        "claims",
        help="List canon claims for a character.",
    )
    list_claims.add_argument("--character-id", required=True, help="Character id.")
    list_claims.add_argument(
        "--status",
        choices=[status.value for status in ClaimStatus],
        default=None,
        help="Optional claim status filter.",
    )
    list_claims.add_argument(
        "--claim-type",
        choices=[claim_type.value for claim_type in ClaimType],
        default=None,
        help="Optional claim type filter.",
    )
    list_claims.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    list_failure_cases = list_subparsers.add_parser(
        "failure-cases",
        help="List critic failure cases.",
    )
    list_failure_cases.add_argument(
        "--category",
        default=None,
        help="Optional failure category filter, usually retry or log.",
    )
    list_failure_cases.add_argument(
        "--conversation-id",
        default=None,
        help="Optional conversation id filter.",
    )
    list_failure_cases.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of failure cases to print.",
    )
    list_failure_cases.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    list_eval_runs = list_subparsers.add_parser(
        "eval-runs",
        help="List evaluation runs.",
    )
    list_eval_runs.add_argument(
        "--character-id",
        default=None,
        help="Optional character id filter.",
    )
    list_eval_runs.add_argument(
        "--test-suite",
        default=None,
        help="Optional test suite filter.",
    )
    list_eval_runs.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of evaluation runs to print.",
    )
    list_eval_runs.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    list_llm_traces = list_subparsers.add_parser(
        "llm-traces",
        help="List structured LLM trace records.",
    )
    list_llm_traces.add_argument(
        "--operation",
        default=None,
        help="Optional operation filter.",
    )
    list_llm_traces.add_argument(
        "--schema-name",
        default=None,
        help="Optional schema name filter.",
    )
    list_llm_traces.add_argument(
        "--provider-name",
        default=None,
        help="Optional provider name filter.",
    )
    list_llm_traces.add_argument(
        "--model-name",
        default=None,
        help="Optional model name filter.",
    )
    list_llm_traces.add_argument(
        "--with-errors",
        action="store_true",
        help="Only include traces with validation errors.",
    )
    list_llm_traces.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of trace records to print.",
    )
    list_llm_traces.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    list_retrieval_eval_runs = list_subparsers.add_parser(
        "retrieval-eval-runs",
        help="List retrieval evaluation runs.",
    )
    list_retrieval_eval_runs.add_argument(
        "--character-id",
        default=None,
        help="Optional character id filter.",
    )
    list_retrieval_eval_runs.add_argument(
        "--source-work-id",
        default=None,
        help="Optional source work id filter.",
    )
    list_retrieval_eval_runs.add_argument(
        "--test-suite",
        default=None,
        help="Optional test suite filter.",
    )
    list_retrieval_eval_runs.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of retrieval evaluation runs to print.",
    )
    list_retrieval_eval_runs.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )

    archive_parser = subparsers.add_parser("archive", help="Archive persisted resources.")
    archive_subparsers = archive_parser.add_subparsers(dest="resource")
    archive_memory = archive_subparsers.add_parser("memory", help="Archive a memory.")
    archive_memory.add_argument("memory_id", help="Memory id.")
    archive_memory.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )

    edit_parser = subparsers.add_parser("edit", help="Edit persisted resources.")
    edit_subparsers = edit_parser.add_subparsers(dest="resource")
    edit_memory = edit_subparsers.add_parser("memory", help="Edit a memory.")
    edit_memory.add_argument("memory_id", help="Memory id.")
    edit_memory.add_argument("--content", required=True, help="Corrected memory content.")
    edit_memory.add_argument(
        "--reason",
        default="User corrected this memory.",
        help="Reason recorded for the correction.",
    )
    edit_memory.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )

    review_parser = subparsers.add_parser("review", help="Review persisted resources.")
    review_subparsers = review_parser.add_subparsers(dest="resource")
    review_memory = review_subparsers.add_parser("memory", help="Accept or reject a candidate memory.")
    review_memory.add_argument("memory_id", help="Memory id.")
    review_memory.add_argument(
        "--decision",
        choices=("accept", "reject"),
        required=True,
        help="Review decision for a candidate memory.",
    )
    review_memory.add_argument("--reason", required=True, help="Reason recorded for the review.")
    review_memory.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )

    summarize_parser = subparsers.add_parser(
        "summarize",
        help="Summarize persisted resources.",
    )
    summarize_subparsers = summarize_parser.add_subparsers(dest="resource")
    summarize_conversation_parser = summarize_subparsers.add_parser(
        "conversation",
        help="Summarize a conversation into its stored summary field.",
    )
    summarize_conversation_parser.add_argument("conversation_id", help="Existing conversation id.")
    summarize_conversation_parser.add_argument(
        "--messages",
        type=int,
        default=20,
        help="Maximum number of recent messages to include.",
    )
    summarize_conversation_parser.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    summarize_conversation_parser.add_argument(
        "--provider",
        choices=("stub", "env"),
        default="stub",
        help="LLM provider source: stub for deterministic local output, env for PJ_* settings.",
    )

    show_parser = subparsers.add_parser("show", help="Show a persisted resource.")
    show_subparsers = show_parser.add_subparsers(dest="resource")
    show_conversation = show_subparsers.add_parser(
        "conversation",
        help="Show conversation details and recent messages.",
    )
    show_conversation.add_argument("conversation_id", help="Existing conversation id.")
    show_conversation.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    show_conversation.add_argument(
        "--messages",
        type=int,
        default=10,
        help="Maximum number of recent messages to print.",
    )
    show_context = show_subparsers.add_parser(
        "context-package",
        help="Show a stored context package.",
    )
    show_context.add_argument("context_package_id", help="Context package id.")
    show_context.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    show_critic = show_subparsers.add_parser(
        "critic-report",
        help="Show a stored critic report.",
    )
    show_critic.add_argument("critic_report_id", help="Critic report id.")
    show_critic.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    show_character = show_subparsers.add_parser(
        "character",
        help="Show a character profile summary.",
    )
    show_character.add_argument("character_id", help="Character id.")
    show_character.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    show_failure_case = show_subparsers.add_parser(
        "failure-case",
        help="Show a stored critic failure case.",
    )
    show_failure_case.add_argument("failure_case_id", help="Failure case id.")
    show_failure_case.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    show_eval_run = show_subparsers.add_parser(
        "eval-run",
        help="Show a stored evaluation run.",
    )
    show_eval_run.add_argument("run_id", help="Evaluation run id.")
    show_eval_run.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    show_llm_trace = show_subparsers.add_parser(
        "llm-trace",
        help="Show a structured LLM trace record.",
    )
    show_llm_trace.add_argument("trace_id", help="LLM raw output trace id.")
    show_llm_trace.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    show_retrieval_eval_run = show_subparsers.add_parser(
        "retrieval-eval-run",
        help="Show a stored retrieval evaluation run.",
    )
    show_retrieval_eval_run.add_argument("run_id", help="Retrieval evaluation run id.")
    show_retrieval_eval_run.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )

    eval_parser = subparsers.add_parser("eval", help="Run evaluation tasks.")
    eval_subparsers = eval_parser.add_subparsers(dest="resource")
    ooc_benchmark = eval_subparsers.add_parser(
        "ooc-benchmark",
        help="Run the MVP OOC and canon pollution benchmark.",
    )
    ooc_benchmark.add_argument("--character-id", required=True, help="Character id to evaluate.")
    ooc_benchmark.add_argument(
        "--persona-version-id",
        default=None,
        help="Persona version id. Defaults to the latest version for the character.",
    )
    ooc_benchmark.add_argument(
        "--test-suite",
        default="mvp_default",
        help="Test suite label to record with the run.",
    )
    ooc_benchmark.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    ooc_benchmark.add_argument(
        "--provider",
        choices=("stub", "env"),
        default="stub",
        help="LLM provider source: stub for deterministic local output, env for PJ_* settings.",
    )
    retrieval_benchmark = eval_subparsers.add_parser(
        "retrieval-benchmark",
        help="Run source retrieval quality benchmark cases.",
    )
    retrieval_benchmark.add_argument("--character-id", required=True, help="Character id to evaluate.")
    retrieval_benchmark.add_argument(
        "--test-suite",
        default="retrieval_default",
        help="Test suite label to record with the run.",
    )
    retrieval_benchmark.add_argument(
        "--max-cases",
        type=int,
        default=20,
        help="Maximum number of verified-claim evidence cases to generate.",
    )
    retrieval_benchmark.add_argument(
        "--no-empty-case",
        action="store_true",
        help="Skip the empty-result fallback case.",
    )
    retrieval_benchmark.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    retrieval_benchmark.add_argument(
        "--provider",
        choices=("stub", "env"),
        default="stub",
        help="Embedding provider source: stub for deterministic local fallback, env for PJ_* settings.",
    )

    db_parser = subparsers.add_parser("db", help="Manage database schema migrations.")
    db_subparsers = db_parser.add_subparsers(dest="resource")
    db_status = db_subparsers.add_parser("status", help="Show database migration status.")
    db_status.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )
    db_migrate = db_subparsers.add_parser("migrate", help="Apply pending database migrations.")
    db_migrate.add_argument(
        "--database-url",
        default=None,
        help="Database URL. Defaults to PJ_DATABASE_URL or sqlite:///personality_jelly.db.",
    )

    config_parser = subparsers.add_parser("config", help="Inspect runtime configuration.")
    config_subparsers = config_parser.add_subparsers(dest="resource")
    config_subparsers.add_parser("show", help="Show sanitized runtime configuration.")
    return parser


def _run_demo(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    provider, model_config = _resolve_demo_provider(args.provider, settings=settings)
    embedding_provider, embedding_config = _resolve_embedding_provider(
        args.provider,
        settings=settings,
    )
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        demo_context = _prepare_demo_persona(
            session,
            args=args,
            provider=provider,
            model_config=model_config,
        )
        user = _resolve_demo_user(
            session,
            display_name=args.user,
            reuse_existing=args.reuse_existing,
        )
        conversation = _resolve_demo_conversation(
            session,
            user_id=user.id,
            character_id=demo_context.character.id,
            persona_version_id=demo_context.persona_version.id,
            reuse_existing=args.reuse_existing,
        )
        turn = send_roleplay_turn(
            session,
            conversation_id=conversation.id,
            content=args.user_message,
            providers=RoleplayTurnProviders(
                roleplay=provider,
                critic=provider,
                memory_curator=provider,
                mode_classifier=provider,
                retriever=embedding_provider,
            ),
            model_configs=RoleplayTurnModelConfigs(
                roleplay=model_config,
                critic=model_config,
                memory_curator=model_config,
                mode_classifier=model_config,
                retrieval_embedding=embedding_config,
            ),
            interaction_mode=(
                InteractionMode(args.interaction_mode)
                if args.interaction_mode is not None
                else None
            ),
            retry_on_critic=args.retry_on_critic,
        )
        session.commit()

    print(f"database_url={database_url}")
    print(f"source_work_id={demo_context.source_work.id}")
    print(f"character_id={demo_context.character.id}")
    print(f"persona_version_id={demo_context.persona_version.id}")
    print(f"conversation_id={conversation.id}")
    print(f"context_package_id={turn.context_package.id}")
    print(f"user_message_id={turn.user_message.id}")
    print(f"assistant_message_id={turn.assistant_message.id}")
    print(f"assistant={turn.assistant_message.content}")
    print(f"critic_report_id={turn.critic_report.id if turn.critic_report else 'none'}")
    print(f"critic_action={turn.critic_report.suggested_action if turn.critic_report else 'none'}")
    print(f"retry_count={turn.retry_count}")
    print(
        "rejected_assistant_message_id="
        f"{turn.rejected_assistant_message.id if turn.rejected_assistant_message else 'none'}"
    )
    print(
        "rejected_critic_report_id="
        f"{turn.rejected_critic_report.id if turn.rejected_critic_report else 'none'}"
    )
    print(f"failure_case_count={len(turn.failure_cases)}")
    for index, failure_case in enumerate(turn.failure_cases, start=1):
        print(f"failure_case.{index}.id={failure_case.id}")
        print(f"failure_case.{index}.category={failure_case.category}")
    print(f"memory_count={len(turn.memories)}")
    return 0


def _run_turn(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    provider, model_config = _resolve_demo_provider(args.provider, settings=settings)
    embedding_provider, embedding_config = _resolve_embedding_provider(
        args.provider,
        settings=settings,
    )
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            conversation = ConversationRepository(session).require(args.conversation_id)
        except LookupError as exc:
            raise CliError(str(exc)) from exc
        turn = send_roleplay_turn(
            session,
            conversation_id=conversation.id,
            content=args.message,
            providers=RoleplayTurnProviders(
                roleplay=provider,
                critic=provider,
                memory_curator=provider,
                mode_classifier=provider,
                retriever=embedding_provider,
            ),
            model_configs=RoleplayTurnModelConfigs(
                roleplay=model_config,
                critic=model_config,
                memory_curator=model_config,
                mode_classifier=model_config,
                retrieval_embedding=embedding_config,
            ),
            interaction_mode=(
                InteractionMode(args.interaction_mode)
                if args.interaction_mode is not None
                else None
            ),
            retry_on_critic=args.retry_on_critic,
        )
        session.commit()

    print(f"database_url={database_url}")
    print(f"conversation_id={conversation.id}")
    print(f"context_package_id={turn.context_package.id}")
    print(f"user_message_id={turn.user_message.id}")
    print(f"assistant_message_id={turn.assistant_message.id}")
    print(f"assistant={turn.assistant_message.content}")
    print(f"critic_report_id={turn.critic_report.id if turn.critic_report else 'none'}")
    print(f"critic_action={turn.critic_report.suggested_action if turn.critic_report else 'none'}")
    print(f"retry_count={turn.retry_count}")
    print(
        "rejected_assistant_message_id="
        f"{turn.rejected_assistant_message.id if turn.rejected_assistant_message else 'none'}"
    )
    print(
        "rejected_critic_report_id="
        f"{turn.rejected_critic_report.id if turn.rejected_critic_report else 'none'}"
    )
    print(f"failure_case_count={len(turn.failure_cases)}")
    for index, failure_case in enumerate(turn.failure_cases, start=1):
        print(f"failure_case.{index}.id={failure_case.id}")
        print(f"failure_case.{index}.category={failure_case.category}")
    print(f"memory_count={len(turn.memories)}")
    return 0


def _run_list(args: argparse.Namespace) -> int:
    if args.resource == "conversations":
        return _run_list_conversations(args)
    if args.resource == "memories":
        return _run_list_memories(args)
    if args.resource == "claims":
        return _run_list_claims(args)
    if args.resource == "failure-cases":
        return _run_list_failure_cases(args)
    if args.resource == "eval-runs":
        return _run_list_eval_runs(args)
    if args.resource == "llm-traces":
        return _run_list_llm_traces(args)
    if args.resource == "retrieval-eval-runs":
        return _run_list_retrieval_eval_runs(args)
    raise CliError("list resource is required")


def _run_archive(args: argparse.Namespace) -> int:
    if args.resource == "memory":
        return _run_archive_memory(args)
    raise CliError("archive resource is required")


def _run_edit(args: argparse.Namespace) -> int:
    if args.resource == "memory":
        return _run_edit_memory(args)
    raise CliError("edit resource is required")


def _run_review(args: argparse.Namespace) -> int:
    if args.resource == "memory":
        return _run_review_memory(args)
    raise CliError("review resource is required")


def _run_summarize(args: argparse.Namespace) -> int:
    if args.resource == "conversation":
        return _run_summarize_conversation(args)
    raise CliError("summarize resource is required")


def _run_show(args: argparse.Namespace) -> int:
    if args.resource == "conversation":
        return _run_show_conversation(args)
    if args.resource == "context-package":
        return _run_show_context_package(args)
    if args.resource == "critic-report":
        return _run_show_critic_report(args)
    if args.resource == "character":
        return _run_show_character(args)
    if args.resource == "failure-case":
        return _run_show_failure_case(args)
    if args.resource == "eval-run":
        return _run_show_eval_run(args)
    if args.resource == "llm-trace":
        return _run_show_llm_trace(args)
    if args.resource == "retrieval-eval-run":
        return _run_show_retrieval_eval_run(args)
    raise CliError("show resource is required")


def _run_eval(args: argparse.Namespace) -> int:
    if args.resource == "ooc-benchmark":
        return _run_ooc_benchmark(args)
    if args.resource == "retrieval-benchmark":
        return _run_retrieval_benchmark(args)
    raise CliError("eval resource is required")


def _run_db(args: argparse.Namespace) -> int:
    if args.resource == "status":
        return _run_db_status(args)
    if args.resource == "migrate":
        return _run_db_migrate(args)
    raise CliError("db resource is required")


def _run_db_status(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    status = get_migration_status(engine)

    print(f"database_url={database_url}")
    print(f"current_version={status.current_version or 'none'}")
    print(f"target_version={status.target_version}")
    print(f"migration_table={str(status.has_schema_migrations_table).lower()}")
    print(f"application_tables={str(status.has_application_tables).lower()}")
    print(f"applied_count={len(status.applied)}")
    print(f"pending_count={len(status.pending)}")
    for index, migration in enumerate(status.pending, start=1):
        print(f"pending.{index}.version={migration.version}")
        print(f"pending.{index}.description={migration.description}")
    return 0


def _run_db_migrate(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    result = migrate_database(engine)

    print(f"database_url={database_url}")
    print(f"current_version={result.status.current_version or 'none'}")
    print(f"target_version={result.status.target_version}")
    print(f"baselined_existing_database={str(result.baselined_existing_database).lower()}")
    print(f"applied_count={len(result.applied)}")
    for index, migration in enumerate(result.applied, start=1):
        print(f"applied.{index}.version={migration.version}")
        print(f"applied.{index}.description={migration.description}")
    print(f"pending_count={len(result.status.pending)}")
    return 0


def _run_list_conversations(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise CliError("--limit must be greater than 0")
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        conversations = ConversationRepository(session).list_recent(limit=args.limit)
        users = UserRepository(session)
        characters = CharacterRepository(session)

        print(f"database_url={database_url}")
        print(f"conversation_count={len(conversations)}")
        for index, conversation in enumerate(conversations, start=1):
            user = users.require(conversation.user_id)
            character = characters.require(conversation.character_id)
            print(f"conversation.{index}.id={conversation.id}")
            print(f"conversation.{index}.user={user.display_name or user.id}")
            print(f"conversation.{index}.character={character.canonical_name}")
            print(f"conversation.{index}.mode={conversation.current_mode}")
            print(f"conversation.{index}.persona_version_id={conversation.persona_version_id}")
    return 0


def _run_list_memories(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)
    scope = MemoryScope(args.scope) if args.scope is not None else None
    status = MemoryStatus(args.status) if args.status is not None else None

    with session_factory() as session:
        memories = MemoryRepository(session).list_for_user_character(
            args.user_id,
            args.character_id,
            scope=scope,
            status=status,
        )

        print(f"database_url={database_url}")
        print(f"memory_count={len(memories)}")
        for index, memory in enumerate(memories, start=1):
            print(f"memory.{index}.id={memory.id}")
            print(f"memory.{index}.scope={memory.scope}")
            print(f"memory.{index}.status={memory.status}")
            print(f"memory.{index}.importance={memory.importance}")
            print(f"memory.{index}.content={memory.content}")
            print(f"memory.{index}.reason={memory.reason}")
    return 0


def _run_list_claims(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)
    status = ClaimStatus(args.status) if args.status is not None else None
    claim_type = ClaimType(args.claim_type) if args.claim_type is not None else None

    with session_factory() as session:
        try:
            CharacterRepository(session).require(args.character_id)
        except LookupError as exc:
            raise CliError(str(exc)) from exc

        claims = CanonClaimRepository(session).list_by_character(
            args.character_id,
            status=status,
            claim_type=claim_type,
        )
        evidence_repository = EvidenceRefRepository(session)

        print(f"database_url={database_url}")
        print(f"character_id={args.character_id}")
        print(f"claim_count={len(claims)}")
        for index, claim in enumerate(claims, start=1):
            evidence_refs = evidence_repository.list_by_claim(claim.id)
            print(f"claim.{index}.id={claim.id}")
            print(f"claim.{index}.type={claim.claim_type}")
            print(f"claim.{index}.status={claim.status}")
            print(f"claim.{index}.confidence={claim.confidence}")
            print(f"claim.{index}.evidence_count={len(evidence_refs)}")
            print(f"claim.{index}.content={claim.content}")
            print(f"claim.{index}.reasoning={claim.reasoning or ''}")
    return 0


def _run_list_failure_cases(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise CliError("--limit must be greater than 0")
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = FailureCaseRepository(session)
        if args.conversation_id is not None:
            failure_cases = repository.list_by_conversation(args.conversation_id)
            if args.category is not None:
                failure_cases = [
                    failure_case
                    for failure_case in failure_cases
                    if failure_case.category == args.category
                ]
            failure_cases = failure_cases[: args.limit]
        else:
            failure_cases = repository.list_recent(
                limit=args.limit,
                category=args.category,
            )

        print(f"database_url={database_url}")
        print(f"failure_case_count={len(failure_cases)}")
        for index, failure_case in enumerate(failure_cases, start=1):
            print(f"failure_case.{index}.id={failure_case.id}")
            print(f"failure_case.{index}.category={failure_case.category}")
            print(f"failure_case.{index}.conversation_id={failure_case.conversation_id}")
            print(f"failure_case.{index}.assistant_message_id={failure_case.assistant_message_id}")
            print(f"failure_case.{index}.critic_report_id={failure_case.critic_report_id}")
            print(f"failure_case.{index}.reason={failure_case.reason}")
    return 0


def _run_list_eval_runs(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise CliError("--limit must be greater than 0")
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        runs = EvaluationRunRepository(session).list_recent(
            limit=args.limit,
            character_id=args.character_id,
            test_suite=args.test_suite,
        )

        print(f"database_url={database_url}")
        print(f"eval_run_count={len(runs)}")
        for index, run in enumerate(runs, start=1):
            print(f"eval_run.{index}.id={run.id}")
            print(f"eval_run.{index}.status={run.status}")
            print(f"eval_run.{index}.test_suite={run.test_suite}")
            print(f"eval_run.{index}.character_id={run.character_id}")
            print(f"eval_run.{index}.persona_version_id={run.persona_version_id}")
            print(f"eval_run.{index}.total={run.total_cases}")
            print(f"eval_run.{index}.passed={run.passed_cases}")
            print(f"eval_run.{index}.failed={run.failed_cases}")
    return 0


def _run_list_llm_traces(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise CliError("--limit must be greater than 0")
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        traces = LLMRawOutputRepository(session).list_recent(
            limit=args.limit,
            operation=args.operation,
            schema_name=args.schema_name,
            provider_name=args.provider_name,
            model_name=args.model_name,
            with_errors=args.with_errors,
        )

        print(f"database_url={database_url}")
        print(f"llm_trace_count={len(traces)}")
        for index, trace in enumerate(traces, start=1):
            print(f"llm_trace.{index}.id={trace.id}")
            print(f"llm_trace.{index}.operation={trace.operation}")
            print(f"llm_trace.{index}.schema_name={trace.schema_name}")
            print(f"llm_trace.{index}.provider_name={trace.provider_name}")
            print(f"llm_trace.{index}.model_name={trace.model_name or 'none'}")
            print(f"llm_trace.{index}.validation_error_count={len(trace.validation_errors)}")
            print(f"llm_trace.{index}.created_at={trace.created_at.isoformat()}")
    return 0


def _run_list_retrieval_eval_runs(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise CliError("--limit must be greater than 0")
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        runs = RetrievalEvaluationRunRepository(session).list_recent(
            limit=args.limit,
            character_id=args.character_id,
            source_work_id=args.source_work_id,
            test_suite=args.test_suite,
        )

        print(f"database_url={database_url}")
        print(f"retrieval_eval_run_count={len(runs)}")
        for index, run in enumerate(runs, start=1):
            print(f"retrieval_eval_run.{index}.id={run.id}")
            print(f"retrieval_eval_run.{index}.status={run.status}")
            print(f"retrieval_eval_run.{index}.test_suite={run.test_suite}")
            print(f"retrieval_eval_run.{index}.source_work_id={run.source_work_id}")
            print(f"retrieval_eval_run.{index}.character_id={run.character_id}")
            print(f"retrieval_eval_run.{index}.embedding_model={run.embedding_model or 'none'}")
            print(f"retrieval_eval_run.{index}.total={run.total_cases}")
            print(f"retrieval_eval_run.{index}.passed={run.passed_cases}")
            print(f"retrieval_eval_run.{index}.failed={run.failed_cases}")
    return 0


def _run_show_conversation(args: argparse.Namespace) -> int:
    if args.messages < 0:
        raise CliError("--messages must be 0 or greater")
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            conversation = ConversationRepository(session).require(args.conversation_id)
        except LookupError as exc:
            raise CliError(str(exc)) from exc
        user = UserRepository(session).require(conversation.user_id)
        character = CharacterRepository(session).require(conversation.character_id)
        messages = MessageRepository(session).list_by_conversation(conversation.id)
        recent_messages = messages[-args.messages :] if args.messages else []

        print(f"database_url={database_url}")
        print(f"conversation_id={conversation.id}")
        print(f"user_id={user.id}")
        print(f"user={user.display_name or user.id}")
        print(f"character_id={character.id}")
        print(f"character={character.canonical_name}")
        print(f"persona_version_id={conversation.persona_version_id}")
        print(f"mode={conversation.current_mode}")
        print(f"message_count={len(messages)}")
        for index, message in enumerate(recent_messages, start=1):
            print(f"message.{index}.id={message.id}")
            print(f"message.{index}.role={message.role}")
            print(f"message.{index}.content={message.content}")
    return 0


def _run_show_character(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            character = CharacterRepository(session).require(args.character_id)
            source_work = SourceWorkRepository(session).require(character.source_work_id)
        except LookupError as exc:
            raise CliError(str(exc)) from exc

        persona = PersonaVersionRepository(session).latest_for_character(character.id)
        claims = CanonClaimRepository(session).list_by_character(character.id)
        evidence_repository = EvidenceRefRepository(session)
        status_counts = _claim_status_counts(claims)
        type_counts = _claim_type_counts(claims)
        evidence_count = sum(
            len(evidence_repository.list_by_claim(claim.id))
            for claim in claims
        )

        print(f"database_url={database_url}")
        print(f"character_id={character.id}")
        print(f"canonical_name={character.canonical_name}")
        print(f"aliases={','.join(character.aliases)}")
        print(f"source_work_id={source_work.id}")
        print(f"source_work_title={source_work.title}")
        print(f"latest_persona_version_id={persona.id if persona else 'none'}")
        print(f"latest_persona_version_number={persona.version_number if persona else 'none'}")
        print(f"claim_count={len(claims)}")
        for status in ClaimStatus:
            print(f"claim_status.{status.value}={status_counts[status.value]}")
        for claim_type in ClaimType:
            print(f"claim_type.{claim_type.value}={type_counts[claim_type.value]}")
        print(f"evidence_count={evidence_count}")
        if persona is not None:
            print("core_self<<END")
            print(persona.core_self)
            print("END")
    return 0


def _run_show_context_package(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            context_package = ContextPackageRepository(session).require(args.context_package_id)
        except LookupError as exc:
            raise CliError(str(exc)) from exc

        print(f"database_url={database_url}")
        print(f"context_package_id={context_package.id}")
        print(f"conversation_id={context_package.conversation_id}")
        print(f"interaction_mode={context_package.interaction_mode}")
        print(f"persona_version_id={context_package.persona_version_id}")
        print(f"claim_ids={','.join(context_package.claim_ids)}")
        print(f"memory_ids={','.join(context_package.memory_ids)}")
        print(f"retrieved_chunk_ids={','.join(context_package.retrieved_chunk_ids)}")
        print("assembled_prompt<<END")
        print(context_package.assembled_prompt)
        print("END")
    return 0


def _run_show_critic_report(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            critic_report = CriticReportRepository(session).require(args.critic_report_id)
        except LookupError as exc:
            raise CliError(str(exc)) from exc

        print(f"database_url={database_url}")
        print(f"critic_report_id={critic_report.id}")
        print(f"message_id={critic_report.message_id}")
        print(f"ooc_risk={critic_report.ooc_risk}")
        print(f"fact_risk={critic_report.fact_risk}")
        print(f"memory_risk={critic_report.memory_risk}")
        print(f"mode_risk={critic_report.mode_risk}")
        print(f"suggested_action={critic_report.suggested_action}")
        print("reasons<<END")
        for reason in critic_report.reasons:
            print(f"- {reason}")
        print("END")
    return 0


def _run_show_failure_case(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            failure_case = FailureCaseRepository(session).require(args.failure_case_id)
            user_message = MessageRepository(session).require(failure_case.user_message_id)
            assistant_message = MessageRepository(session).require(failure_case.assistant_message_id)
            critic_report = CriticReportRepository(session).require(failure_case.critic_report_id)
        except LookupError as exc:
            raise CliError(str(exc)) from exc

        print(f"database_url={database_url}")
        print(f"failure_case_id={failure_case.id}")
        print(f"category={failure_case.category}")
        print(f"conversation_id={failure_case.conversation_id}")
        print(f"user_message_id={failure_case.user_message_id}")
        print(f"assistant_message_id={failure_case.assistant_message_id}")
        print(f"context_package_id={failure_case.context_package_id}")
        print(f"critic_report_id={failure_case.critic_report_id}")
        print(f"critic_action={critic_report.suggested_action}")
        print(f"reason={failure_case.reason}")
        print(f"notes={failure_case.notes or ''}")
        print("user_message<<END")
        print(user_message.content)
        print("END")
        print("assistant_message<<END")
        print(assistant_message.content)
        print("END")
    return 0


def _run_show_eval_run(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            run = EvaluationRunRepository(session).require(args.run_id)
        except LookupError as exc:
            raise CliError(str(exc)) from exc
        case_results = EvaluationCaseResultRepository(session).list_by_run(run.id)

        print(f"database_url={database_url}")
        print(f"run_id={run.id}")
        print(f"status={run.status}")
        print(f"test_suite={run.test_suite}")
        print(f"character_id={run.character_id}")
        print(f"persona_version_id={run.persona_version_id}")
        print(f"total={run.total_cases}")
        print(f"passed={run.passed_cases}")
        print(f"failed={run.failed_cases}")
        print(f"case_count={len(case_results)}")
        for index, case_result in enumerate(case_results, start=1):
            print(f"case.{index}.id={case_result.case_id}")
            print(f"case.{index}.status={case_result.status}")
            print(f"case.{index}.interaction_mode={case_result.interaction_mode}")
            print(f"case.{index}.assistant_message_id={case_result.assistant_message_id}")
            print(f"case.{index}.critic_report_id={case_result.critic_report_id or 'none'}")
            print(f"case.{index}.prompt={case_result.prompt}")
            print(f"case.{index}.reasons<<END")
            for reason in case_result.reasons:
                print(f"- {reason}")
            print("END")
    return 0


def _run_show_llm_trace(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            trace = LLMRawOutputRepository(session).require(args.trace_id)
        except LookupError as exc:
            raise CliError(str(exc)) from exc

        print(f"database_url={database_url}")
        print(f"llm_trace_id={trace.id}")
        print(f"operation={trace.operation}")
        print(f"schema_name={trace.schema_name}")
        print(f"provider_name={trace.provider_name}")
        print(f"model_name={trace.model_name or 'none'}")
        print(f"validation_error_count={len(trace.validation_errors)}")
        print(f"created_at={trace.created_at.isoformat()}")
        print("response_schema<<END")
        print(_json_block(trace.response_schema))
        print("END")
        print("raw_output<<END")
        print(trace.raw_output)
        print("END")
        print("parsed_output<<END")
        print(_json_block(trace.parsed_output))
        print("END")
        print("validation_errors<<END")
        for error in trace.validation_errors:
            print(error)
        print("END")
    return 0


def _run_show_retrieval_eval_run(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            run = RetrievalEvaluationRunRepository(session).require(args.run_id)
        except LookupError as exc:
            raise CliError(str(exc)) from exc
        case_results = RetrievalEvaluationCaseResultRepository(session).list_by_run(run.id)

        print(f"database_url={database_url}")
        print(f"run_id={run.id}")
        print(f"status={run.status}")
        print(f"test_suite={run.test_suite}")
        print(f"source_work_id={run.source_work_id}")
        print(f"character_id={run.character_id}")
        print(f"embedding_model={run.embedding_model or 'none'}")
        print(f"total={run.total_cases}")
        print(f"passed={run.passed_cases}")
        print(f"failed={run.failed_cases}")
        print(f"case_count={len(case_results)}")
        for index, case_result in enumerate(case_results, start=1):
            print(f"case.{index}.id={case_result.case_id}")
            print(f"case.{index}.status={case_result.status}")
            print(f"case.{index}.recall={case_result.recall}")
            print(f"case.{index}.first_relevant_rank={case_result.first_relevant_rank or 'none'}")
            print(f"case.{index}.ranking_score={case_result.ranking_score}")
            print(f"case.{index}.expected_chunk_ids={','.join(case_result.expected_chunk_ids)}")
            print(f"case.{index}.retrieved_chunk_ids={','.join(case_result.retrieved_chunk_ids)}")
            print(f"case.{index}.query={case_result.query}")
            print(f"case.{index}.reasons<<END")
            for reason in case_result.reasons:
                print(f"- {reason}")
            print("END")
    return 0


def _run_archive_memory(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            memory = MemoryRepository(session).update_status(
                args.memory_id,
                status=MemoryStatus.ARCHIVED,
            )
        except LookupError as exc:
            raise CliError(str(exc)) from exc
        session.commit()

    print(f"database_url={database_url}")
    print(f"memory_id={memory.id}")
    print(f"status={memory.status}")
    return 0


def _run_edit_memory(args: argparse.Namespace) -> int:
    content = args.content.strip()
    if not content:
        raise CliError("--content cannot be empty")
    reason = args.reason.strip()
    if not reason:
        raise CliError("--reason cannot be empty")

    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            memory = MemoryRepository(session).update_content(
                args.memory_id,
                content=content,
                reason=reason,
            )
        except LookupError as exc:
            raise CliError(str(exc)) from exc
        session.commit()

    print(f"database_url={database_url}")
    print(f"memory_id={memory.id}")
    print(f"status={memory.status}")
    print(f"content={memory.content}")
    print(f"reason={memory.reason}")
    return 0


def _run_review_memory(args: argparse.Namespace) -> int:
    reason = args.reason.strip()
    if not reason:
        raise CliError("--reason cannot be empty")
    target_status = (
        MemoryStatus.ACCEPTED
        if args.decision == "accept"
        else MemoryStatus.REJECTED
    )

    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            memory = MemoryRepository(session).review_candidate(
                args.memory_id,
                status=target_status,
                reason=reason,
            )
        except (LookupError, ValueError) as exc:
            raise CliError(str(exc)) from exc
        session.commit()

    print(f"database_url={database_url}")
    print(f"memory_id={memory.id}")
    print(f"status={memory.status}")
    print(f"reason={memory.reason}")
    return 0


def _run_summarize_conversation(args: argparse.Namespace) -> int:
    if args.messages < 1:
        raise CliError("--messages must be greater than 0")
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    provider, model_config = _resolve_demo_provider(args.provider, settings=settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            result = summarize_conversation(
                session,
                conversation_id=args.conversation_id,
                provider=provider,
                model_config=model_config,
                max_messages=args.messages,
            )
        except (LookupError, ValueError) as exc:
            raise CliError(str(exc)) from exc
        session.commit()

    print(f"database_url={database_url}")
    print(f"conversation_id={result.conversation.id}")
    print(f"summary={result.conversation.summary}")
    return 0


def _run_ooc_benchmark(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    provider, model_config = _resolve_demo_provider(args.provider, settings=settings)
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            result = run_ooc_benchmark(
                session,
                character_id=args.character_id,
                persona_version_id=args.persona_version_id,
                provider=provider,
                model_config=model_config,
                test_suite=args.test_suite,
            )
        except (LookupError, ValueError) as exc:
            raise CliError(str(exc)) from exc
        session.commit()

    print(f"database_url={database_url}")
    print(f"run_id={result.run.id}")
    print(f"status={result.run.status}")
    print(f"test_suite={result.run.test_suite}")
    print(f"character_id={result.run.character_id}")
    print(f"persona_version_id={result.run.persona_version_id}")
    print(f"total={result.run.total_cases}")
    print(f"passed={result.run.passed_cases}")
    print(f"failed={result.run.failed_cases}")
    for index, case_result in enumerate(result.case_results, start=1):
        print(f"case.{index}.id={case_result.case_id}")
        print(f"case.{index}.status={case_result.status}")
        print(f"case.{index}.critic_report_id={case_result.critic_report_id or 'none'}")
    return 0


def _run_retrieval_benchmark(args: argparse.Namespace) -> int:
    if args.max_cases < 1:
        raise CliError("--max-cases must be greater than 0")
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    if args.provider == "stub":
        embedding_provider: LLMProvider | None = StubProvider()
        embedding_config: EmbeddingConfig | None = EmbeddingConfig(model="stub-embedding")
    else:
        embedding_provider, embedding_config = _resolve_embedding_provider(
            args.provider,
            settings=settings,
        )
    engine = create_database_engine(database_url)
    ensure_database_ready(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            result = run_retrieval_benchmark(
                session,
                character_id=args.character_id,
                provider=embedding_provider,
                embedding_config=embedding_config,
                test_suite=args.test_suite,
                max_cases=args.max_cases,
                include_empty_case=not args.no_empty_case,
            )
        except (LookupError, ValueError) as exc:
            raise CliError(str(exc)) from exc
        session.commit()

    print(f"database_url={database_url}")
    print(f"run_id={result.run.id}")
    print(f"status={result.run.status}")
    print(f"test_suite={result.run.test_suite}")
    print(f"source_work_id={result.run.source_work_id}")
    print(f"character_id={result.run.character_id}")
    print(f"embedding_model={result.run.embedding_model or 'none'}")
    print(f"total={result.run.total_cases}")
    print(f"passed={result.run.passed_cases}")
    print(f"failed={result.run.failed_cases}")
    for index, case_result in enumerate(result.case_results, start=1):
        print(f"case.{index}.id={case_result.case_id}")
        print(f"case.{index}.status={case_result.status}")
        print(f"case.{index}.recall={case_result.recall}")
        print(f"case.{index}.first_relevant_rank={case_result.first_relevant_rank or 'none'}")
    return 0


def _run_config(args: argparse.Namespace) -> int:
    if args.resource == "show":
        return _run_config_show(args)
    raise CliError("config resource is required")


def _run_config_show(args: argparse.Namespace) -> int:
    settings = Settings()
    print(f"config_file={settings.resolved_config_file}")
    print(f"database_url={settings.database_url}")
    print(f"default_language={settings.default_language}")
    print(f"log_level={settings.log_level}")
    print(f"llm.provider={_display_value(settings.llm_provider)}")
    print(f"llm.base_url={settings.llm_base_url}")
    print(f"llm.model={_display_value(settings.llm_model)}")
    print(f"llm.timeout_seconds={settings.llm_timeout_seconds:g}")
    print(f"llm.json_response_format={settings.llm_json_response_format}")
    print(f"llm.api_key_configured={_bool_text(bool(settings.llm_api_key))}")
    embedding_provider = settings.embedding_provider or settings.llm_provider
    print(f"embedding.provider={_display_value(embedding_provider)}")
    print(f"embedding.base_url={settings.embedding_base_url or settings.llm_base_url}")
    print(f"embedding.model={_display_value(settings.embedding_model)}")
    print(
        "embedding.timeout_seconds="
        f"{(settings.embedding_timeout_seconds or settings.llm_timeout_seconds):g}"
    )
    print(
        "embedding.api_key_configured="
        f"{_bool_text(bool(settings.embedding_api_key or settings.llm_api_key))}"
    )
    return 0


def _resolve_database_url(args: argparse.Namespace, settings: Settings) -> str:
    memory_db = getattr(args, "memory_db", False)
    if memory_db and args.database_url:
        raise CliError("--memory-db cannot be combined with --database-url")
    if memory_db:
        return "sqlite:///:memory:"
    return args.database_url or settings.database_url


def _resolve_embedding_config(settings: Settings) -> EmbeddingConfig | None:
    embedding_model = settings.embedding_model.strip() if settings.embedding_model else ""
    if not embedding_model:
        return None
    return EmbeddingConfig(model=embedding_model)


def _resolve_embedding_provider(
    provider_source: str,
    *,
    settings: Settings | None = None,
) -> tuple[LLMProvider | None, EmbeddingConfig | None]:
    embedding_config = _resolve_embedding_config(settings or Settings())
    if embedding_config is None:
        return None, None
    if provider_source == "stub":
        return StubProvider(), embedding_config
    if provider_source == "env":
        active_settings = settings or Settings()
        try:
            return build_embedding_provider(active_settings), embedding_config
        except ValueError as exc:
            raise CliError(str(exc)) from exc
    raise CliError(f"unsupported provider source {provider_source!r}")


def _resolve_demo_provider(
    provider_source: str,
    *,
    settings: Settings | None = None,
) -> tuple[LLMProvider, ModelConfig]:
    if provider_source == "stub":
        return StubProvider(), ModelConfig(model="stub")

    if provider_source == "env":
        active_settings = settings or Settings()
        llm_model = active_settings.llm_model.strip() if active_settings.llm_model else ""
        if not llm_model:
            raise CliError("PJ_LLM_MODEL is required when using --provider env")
        try:
            provider = build_llm_provider(active_settings)
        except ValueError as exc:
            raise CliError(str(exc)) from exc
        return provider, ModelConfig(model=llm_model)

    raise CliError(f"unsupported provider source {provider_source!r}")


def _display_value(value: str | None) -> str:
    if value is None or not value.strip():
        return "none"
    return value


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _json_block(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _prepare_demo_persona(
    session,
    *,
    args: argparse.Namespace,
    provider: LLMProvider,
    model_config: ModelConfig,
) -> DemoPersonaContext:
    source_work = None
    if args.reuse_existing:
        loaded_title = args.source.stem
        source_work = SourceWorkRepository(session).find_by_title(loaded_title)

    if source_work is None:
        ingestion = ingest_text_file(session, args.source)
        source_work = ingestion.source_work
    else:
        ingestion = SourceIngestionResult(source_work=source_work, chunks=[])

    character_repository = CharacterRepository(session)
    character = (
        character_repository.find_by_source_work_and_name(source_work.id, args.character)
        if args.reuse_existing
        else None
    )
    if character is None:
        character = create_character(
            session,
            source_work_id=source_work.id,
            canonical_name=args.character,
            aliases=args.alias,
        ).character

    persona = (
        PersonaVersionRepository(session).latest_for_character(character.id)
        if args.reuse_existing
        else None
    )
    if persona is not None:
        return DemoPersonaContext(
            source_work=ingestion.source_work,
            character=character,
            persona_version=persona,
        )

    run_reader_extraction(
        session,
        provider=provider,
        model_config=model_config,
        character_id=character.id,
    )
    verify_candidate_claims(
        session,
        provider=provider,
        model_config=model_config,
        character=CharacterRepository(session).require(character.id),
    )
    persona = compile_persona_version(
        session,
        provider=provider,
        model_config=model_config,
        character_id=character.id,
    ).persona_version
    return DemoPersonaContext(
        source_work=ingestion.source_work,
        character=character,
        persona_version=persona,
    )


def _resolve_demo_user(session, *, display_name: str, reuse_existing: bool) -> User:
    user = UserRepository(session).find_by_display_name(display_name) if reuse_existing else None
    return user or create_user(session, display_name=display_name).user


def _resolve_demo_conversation(
    session,
    *,
    user_id: str,
    character_id: str,
    persona_version_id: str,
    reuse_existing: bool,
) -> Conversation:
    conversation = (
        ConversationRepository(session).latest_for_user_character(user_id, character_id)
        if reuse_existing
        else None
    )
    return conversation or create_conversation(
        session,
        user_id=user_id,
        character_id=character_id,
        persona_version_id=persona_version_id,
    ).conversation


def _claim_status_counts(claims) -> dict[str, int]:
    counts = {status.value: 0 for status in ClaimStatus}
    for claim in claims:
        counts[str(claim.status)] += 1
    return counts


def _claim_type_counts(claims) -> dict[str, int]:
    counts = {claim_type.value: 0 for claim_type in ClaimType}
    for claim in claims:
        counts[str(claim.claim_type)] += 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
