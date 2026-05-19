from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from personality_jelly.characters import create_character
from personality_jelly.core import Settings
from personality_jelly.domain import Character, Conversation, PersonaVersion, SourceWork, User
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.ingestion import SourceIngestionResult, ingest_text_file
from personality_jelly.llm import LLMProvider, ModelConfig, build_llm_provider
from personality_jelly.runtime import (
    RoleplayTurnModelConfigs,
    RoleplayTurnProviders,
    create_conversation,
    create_user,
    send_roleplay_turn,
)
from personality_jelly.persona import compile_persona_version
from personality_jelly.storage import create_all, create_database_engine, create_session_factory
from personality_jelly.storage.repositories import (
    CharacterRepository,
    ConversationRepository,
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
        "--provider",
        choices=("stub", "env"),
        default="stub",
        help="LLM provider source: stub for deterministic local output, env for PJ_* settings.",
    )

    turn = subparsers.add_parser("turn", help="Send one message to an existing conversation.")
    turn.add_argument("conversation_id", help="Existing conversation id.")
    turn.add_argument("--message", required=True, help="User message content.")
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
        )
        session.commit()

    print(f"database_url={database_url}")
    print(f"source_work_id={demo_context.source_work.id}")
    print(f"character_id={demo_context.character.id}")
    print(f"persona_version_id={demo_context.persona_version.id}")
    print(f"conversation_id={conversation.id}")
    print(f"assistant={turn.assistant_message.content}")
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
        )
        session.commit()

    print(f"database_url={database_url}")
    print(f"conversation_id={conversation.id}")
    print(f"user_message_id={turn.user_message.id}")
    print(f"assistant_message_id={turn.assistant_message.id}")
    print(f"assistant={turn.assistant_message.content}")
    print(f"critic_action={turn.critic_report.suggested_action if turn.critic_report else 'none'}")
    print(f"memory_count={len(turn.memories)}")
    return 0


def _run_list(args: argparse.Namespace) -> int:
    if args.resource == "conversations":
        return _run_list_conversations(args)
    raise CliError("list resource is required")


def _run_show(args: argparse.Namespace) -> int:
    if args.resource == "conversation":
        return _run_show_conversation(args)
    raise CliError("show resource is required")


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


if __name__ == "__main__":
    raise SystemExit(main())

