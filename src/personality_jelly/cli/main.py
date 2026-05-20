from __future__ import annotations

import argparse
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
from personality_jelly.evaluation import run_ooc_benchmark
from personality_jelly.ingestion import SourceIngestionResult, ingest_text_file
from personality_jelly.llm import LLMProvider, ModelConfig, build_llm_provider
from personality_jelly.runtime import (
    RoleplayTurnModelConfigs,
    RoleplayTurnProviders,
    create_conversation,
    create_user,
    send_roleplay_turn,
    summarize_conversation,
)
from personality_jelly.persona import compile_persona_version
from personality_jelly.storage import create_all, create_database_engine, create_session_factory
from personality_jelly.storage.repositories import (
    CharacterRepository,
    CanonClaimRepository,
    ConversationRepository,
    ContextPackageRepository,
    CriticReportRepository,
    EvidenceRefRepository,
    MemoryRepository,
    MessageRepository,
    PersonaVersionRepository,
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
        if args.command == "summarize":
            return _run_summarize(args)
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
    return parser


def _run_demo(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    provider, model_config = _resolve_demo_provider(args.provider, settings=settings)
    engine = create_database_engine(database_url)
    create_all(engine)
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
            ),
            model_configs=RoleplayTurnModelConfigs(
                roleplay=model_config,
                critic=model_config,
                memory_curator=model_config,
            ),
            interaction_mode=(
                InteractionMode(args.interaction_mode)
                if args.interaction_mode is not None
                else None
            ),
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
    print(f"memory_count={len(turn.memories)}")
    return 0


def _run_turn(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    provider, model_config = _resolve_demo_provider(args.provider, settings=settings)
    engine = create_database_engine(database_url)
    create_all(engine)
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
            ),
            model_configs=RoleplayTurnModelConfigs(
                roleplay=model_config,
                critic=model_config,
                memory_curator=model_config,
            ),
            interaction_mode=(
                InteractionMode(args.interaction_mode)
                if args.interaction_mode is not None
                else None
            ),
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
    print(f"memory_count={len(turn.memories)}")
    return 0


def _run_list(args: argparse.Namespace) -> int:
    if args.resource == "conversations":
        return _run_list_conversations(args)
    if args.resource == "memories":
        return _run_list_memories(args)
    if args.resource == "claims":
        return _run_list_claims(args)
    raise CliError("list resource is required")


def _run_archive(args: argparse.Namespace) -> int:
    if args.resource == "memory":
        return _run_archive_memory(args)
    raise CliError("archive resource is required")


def _run_edit(args: argparse.Namespace) -> int:
    if args.resource == "memory":
        return _run_edit_memory(args)
    raise CliError("edit resource is required")


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
    raise CliError("show resource is required")


def _run_eval(args: argparse.Namespace) -> int:
    if args.resource == "ooc-benchmark":
        return _run_ooc_benchmark(args)
    raise CliError("eval resource is required")


def _run_list_conversations(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise CliError("--limit must be greater than 0")
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    create_all(engine)
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
    create_all(engine)
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
    create_all(engine)
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


def _run_show_conversation(args: argparse.Namespace) -> int:
    if args.messages < 0:
        raise CliError("--messages must be 0 or greater")
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    create_all(engine)
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
    create_all(engine)
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
    create_all(engine)
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
    create_all(engine)
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


def _run_archive_memory(args: argparse.Namespace) -> int:
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    engine = create_database_engine(database_url)
    create_all(engine)
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
    create_all(engine)
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


def _run_summarize_conversation(args: argparse.Namespace) -> int:
    if args.messages < 1:
        raise CliError("--messages must be greater than 0")
    settings = Settings()
    database_url = _resolve_database_url(args, settings)
    provider, model_config = _resolve_demo_provider(args.provider, settings=settings)
    engine = create_database_engine(database_url)
    create_all(engine)
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
    create_all(engine)
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


def _resolve_database_url(args: argparse.Namespace, settings: Settings) -> str:
    memory_db = getattr(args, "memory_db", False)
    if memory_db and args.database_url:
        raise CliError("--memory-db cannot be combined with --database-url")
    if memory_db:
        return "sqlite:///:memory:"
    return args.database_url or settings.database_url


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

