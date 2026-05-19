from __future__ import annotations

import argparse
import sys
from pathlib import Path

from personality_jelly.characters import create_character
from personality_jelly.core import Settings
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.ingestion import ingest_text_file
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
from personality_jelly.storage.repositories import CharacterRepository
from personality_jelly.testing.stub_provider import StubProvider


class CliError(Exception):
    """User-facing CLI error."""


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            return _run_demo(args)
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
    demo.add_argument("--database-url", default="sqlite:///:memory:")
    demo.add_argument(
        "--provider",
        choices=("stub", "env"),
        default="stub",
        help="LLM provider source: stub for deterministic local output, env for PJ_* settings.",
    )
    return parser


def _run_demo(args: argparse.Namespace) -> int:
    engine = create_database_engine(args.database_url)
    create_all(engine)
    session_factory = create_session_factory(engine)
    provider, model_config = _resolve_demo_provider(args.provider)

    with session_factory() as session:
        ingestion = ingest_text_file(session, args.source)
        character = create_character(
            session,
            source_work_id=ingestion.source_work.id,
            canonical_name=args.character,
            aliases=args.alias,
        ).character
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
        user = create_user(session, display_name="demo-user").user
        conversation = create_conversation(
            session,
            user_id=user.id,
            character_id=character.id,
            persona_version_id=persona.id,
        ).conversation
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

    print(f"source_work_id={ingestion.source_work.id}")
    print(f"character_id={character.id}")
    print(f"persona_version_id={persona.id}")
    print(f"conversation_id={conversation.id}")
    print(f"assistant={turn.assistant_message.content}")
    print(f"critic_action={turn.critic_report.suggested_action if turn.critic_report else 'none'}")
    print(f"memory_count={len(turn.memories)}")
    return 0


def _resolve_demo_provider(provider_source: str) -> tuple[LLMProvider, ModelConfig]:
    if provider_source == "stub":
        return StubProvider(), ModelConfig(model="stub")

    if provider_source == "env":
        settings = Settings()
        llm_model = settings.llm_model.strip() if settings.llm_model else ""
        if not llm_model:
            raise CliError("PJ_LLM_MODEL is required when using --provider env")
        try:
            provider = build_llm_provider(settings)
        except ValueError as exc:
            raise CliError(str(exc)) from exc
        return provider, ModelConfig(model=llm_model)

    raise CliError(f"unsupported provider source {provider_source!r}")


if __name__ == "__main__":
    raise SystemExit(main())

