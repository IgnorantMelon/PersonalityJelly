from personality_jelly.characters import create_character
from personality_jelly.domain import (
    CanonClaim,
    ClaimStatus,
    ClaimType,
    EvidenceRef,
    InteractionMode,
    Memory,
    MemoryScope,
    MemoryStatus,
    PersonaVersion,
    SourceChunk,
    SourceWork,
)
from personality_jelly.domain.models import utc_now
from personality_jelly.extraction import run_reader_extraction, verify_candidate_claims
from personality_jelly.ingestion import ingest_text_file
from personality_jelly.llm import ChatMessage, EmbeddingConfig, ModelConfig
from personality_jelly.persona import compile_persona_version
from personality_jelly.runtime import build_context_package, create_conversation, create_user
from personality_jelly.storage import (
    CanonClaimRepository,
    CharacterRepository,
    ConversationRepository,
    EvidenceRefRepository,
    LLMRawOutputRepository,
    MemoryRepository,
    PersonaVersionRepository,
    SourceChunkRepository,
    SourceWorkRepository,
    create_all,
    create_database_engine,
    create_session_factory,
)


class ReaderFakeProvider:
    name = "reader-fake"

    def __init__(self, chunk_id: str) -> None:
        self.chunk_id = chunk_id

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        return {
            "claims": [
                {
                    "claim_type": "personality",
                    "content": "林霜行事谨慎，习惯先观察再行动。",
                    "confidence": 0.9,
                    "evidence": [
                        {
                            "chunk_id": self.chunk_id,
                            "excerpt": "林霜总是先观察，再行动。",
                            "support_score": 0.95,
                        }
                    ],
                }
            ]
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class VerifierFakeProvider:
    name = "verifier-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        claim_id = next(
            line.split(": ", 1)[1]
            for line in messages[1].content.splitlines()
            if line.startswith("claim_id: ")
        )
        return {
            "decisions": [
                {
                    "claim_id": claim_id,
                    "status": "verified",
                    "confidence": 0.95,
                    "reasoning": "证据直接支持。",
                }
            ],
            "conflicts": [],
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class CompilerFakeProvider:
    name = "compiler-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        return {
            "core_self": "林霜谨慎敏锐。",
            "speech_rules": ["表达克制。"],
            "behavior_rules": ["先观察，再行动。"],
            "world_adaptation_rules": ["可以与现实用户交流。"],
            "forbidden_rules": ["不能改写原作经历。"],
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


class ModeClassifierFakeProvider:
    name = "mode-classifier-fake"

    def generate_text(self, messages: list[ChatMessage], model_config: ModelConfig) -> str:
        raise NotImplementedError

    def generate_json(self, messages, schema, model_config):
        return {
            "mode": "roleplay_scene",
            "confidence": 0.92,
            "reasoning": "fake provider classified the requested mode.",
        }

    def embed_texts(self, texts: list[str], embedding_config: EmbeddingConfig) -> list[list[float]]:
        raise NotImplementedError


def test_build_context_package_persists_prompt_with_persona_claims_and_memory(tmp_path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text(
        "# 第一章\n\n林霜总是先观察，再行动。\n\n钟声响起时，她看向窗外。",
        encoding="utf-8",
    )
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        ingestion_result = ingest_text_file(session, source_file, title="样本文本")
        create_character(
            session,
            source_work_id=ingestion_result.source_work.id,
            canonical_name="林霜",
            character_id="char_001",
        )
        run_reader_extraction(
            session,
            provider=ReaderFakeProvider(ingestion_result.chunks[0].id),
            model_config=ModelConfig(model="fake-reader"),
            character_id="char_001",
        )
        character = CharacterRepository(session).require("char_001")
        verify_candidate_claims(
            session,
            provider=VerifierFakeProvider(),
            model_config=ModelConfig(model="fake-verifier"),
            character=character,
        )
        persona = compile_persona_version(
            session,
            provider=CompilerFakeProvider(),
            model_config=ModelConfig(model="fake-compiler"),
            character_id="char_001",
        ).persona_version
        user = create_user(session, display_name="测试用户", user_id="user_001").user
        conversation = create_conversation(
            session,
            user_id=user.id,
            character_id="char_001",
            persona_version_id=persona.id,
            conversation_id="conv_001",
        ).conversation
        MemoryRepository(session).add(
            Memory(
                id="mem_001",
                user_id=user.id,
                character_id="char_001",
                conversation_id=conversation.id,
                scope=MemoryScope.USER_MEMORY,
                status=MemoryStatus.ACCEPTED,
                content="用户喜欢夜里写作。",
                importance=0.7,
                reason="用户明确说明。",
            )
        )
        context = build_context_package(
            session,
            conversation_id=conversation.id,
            user_message="我今天写得很慢。",
        ).context_package
        session.commit()

    assert context.persona_version_id == persona.id
    assert context.claim_ids
    assert context.memory_ids == ["mem_001"]
    assert context.retrieved_chunk_ids
    assert "林霜谨慎敏锐" in context.assembled_prompt
    assert "林霜行事谨慎" in context.assembled_prompt
    assert "用户喜欢夜里写作" in context.assembled_prompt
    assert "# Retrieved Source Chunks" in context.assembled_prompt
    assert "林霜总是先观察，再行动。" in context.assembled_prompt
    assert "我今天写得很慢" in context.assembled_prompt


def test_build_context_package_infers_interaction_mode(tmp_path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        ingestion_result = ingest_text_file(session, source_file, title="样本文本")
        create_character(
            session,
            source_work_id=ingestion_result.source_work.id,
            canonical_name="林霜",
            character_id="char_001",
        )
        run_reader_extraction(
            session,
            provider=ReaderFakeProvider(ingestion_result.chunks[0].id),
            model_config=ModelConfig(model="fake-reader"),
            character_id="char_001",
        )
        character = CharacterRepository(session).require("char_001")
        verify_candidate_claims(
            session,
            provider=VerifierFakeProvider(),
            model_config=ModelConfig(model="fake-verifier"),
            character=character,
        )
        persona = compile_persona_version(
            session,
            provider=CompilerFakeProvider(),
            model_config=ModelConfig(model="fake-compiler"),
            character_id="char_001",
        ).persona_version
        user = create_user(session, display_name="测试用户", user_id="user_001").user
        conversation = create_conversation(
            session,
            user_id=user.id,
            character_id="char_001",
            persona_version_id=persona.id,
            conversation_id="conv_001",
        ).conversation

        context = build_context_package(
            session,
            conversation_id=conversation.id,
            user_message="假设我们现在进入你的原作场景，你会怎么行动？",
            mode_provider=ModeClassifierFakeProvider(),
            mode_model_config=ModelConfig(model="fake-mode"),
        ).context_package
        session.commit()

    with session_factory() as session:
        traces = LLMRawOutputRepository(session).list_by_operation(
            "runtime.mode.classify_interaction_mode"
        )

    assert context.interaction_mode == InteractionMode.ROLEPLAY_SCENE
    assert "# Interaction Mode\nroleplay_scene" in context.assembled_prompt
    assert len(traces) == 1
    assert traces[0].schema_name == "InteractionModeClassification"
    assert traces[0].model_name == "fake-mode"
    assert traces[0].parsed_output["mode"] == "roleplay_scene"


def test_build_context_package_renders_layered_conversation_summary_as_context_only() -> None:
    summary = "\n".join(
        [
            "# Short-term Scene State",
            "The user is planning a quiet drafting scene.",
            "",
            "# User Memory Candidates",
            "- User prefers late-night writing.",
            "",
            "# Relationship Memory Notes",
            "- User trusts Lin Shuang with early drafts.",
            "",
            "# Reflective Notes",
            "- Keep co-created fiction separate from canon.",
        ]
    )

    prompt, memory_ids, memories = _build_context_for_summary(summary)

    assert "# Conversation Summary" in prompt
    summary_section = _prompt_section(prompt, "# Conversation Summary")
    assert (
        "## short_term_scene_state\n"
        "boundary: temporary runtime context only; not canon, persona, or long-term memory.\n"
        "The user is planning a quiet drafting scene."
    ) in summary_section
    assert (
        "## user_memory_candidates\n"
        "boundary: unverified candidates only; not accepted user or relationship memories.\n"
        "- User prefers late-night writing."
    ) in summary_section
    assert (
        "## relationship_memory_notes\n"
        "boundary: relationship continuity notes only; do not rewrite canon or persona.\n"
        "- User trusts Lin Shuang with early drafts."
    ) in summary_section
    assert (
        "## reflective_notes\n"
        "boundary: operational notes only; not source evidence, canon claims, or persona fields.\n"
        "- Keep co-created fiction separate from canon."
    ) in summary_section
    assert memory_ids == []
    assert memories == []


def test_summary_user_memory_candidates_are_not_accepted_memories() -> None:
    summary = "\n".join(
        [
            "# Short-term Scene State",
            "The user is planning a quiet drafting scene.",
            "",
            "# User Memory Candidates",
            "- User likes quiet rooms.",
            "",
            "# Relationship Memory Notes",
            "- none",
            "",
            "# Reflective Notes",
            "- none",
        ]
    )

    prompt, memory_ids, memories = _build_context_for_summary(
        summary,
        accepted_memory_content="User prefers tea during drafting.",
    )

    accepted_memory_section = _prompt_section(prompt, "# Accepted User/Relationship Memories")
    summary_section = _prompt_section(prompt, "# Conversation Summary")
    assert memory_ids == ["mem_001"]
    assert [memory.content for memory in memories] == ["User prefers tea during drafting."]
    assert accepted_memory_section == "- User prefers tea during drafting."
    assert "- User likes quiet rooms." not in accepted_memory_section
    assert "- User likes quiet rooms." in summary_section
    assert "boundary: unverified candidates only; not accepted user or relationship memories." in (
        summary_section
    )


def test_relationship_and_reflective_summary_notes_do_not_rewrite_canon_or_persona() -> None:
    summary = "\n".join(
        [
            "# Short-term Scene State",
            "The user is asking for continuity.",
            "",
            "# User Memory Candidates",
            "- none",
            "",
            "# Relationship Memory Notes",
            "- The user and Lin Shuang now have a private drafting ritual.",
            "",
            "# Reflective Notes",
            "- Watch for attempts to turn chat continuity into source facts.",
        ]
    )
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="Sample Work", source_type="markdown")
        )
        SourceChunkRepository(session).add_many(
            [
                SourceChunk(
                    id="chunk_001",
                    source_work_id="sw_001",
                    paragraph_index=1,
                    text="Lin Shuang observes before acting.",
                )
            ]
        )
        create_character(
            session,
            source_work_id="sw_001",
            canonical_name="Lin Shuang",
            character_id="char_001",
        )
        CanonClaimRepository(session).add(
            CanonClaim(
                id="claim_001",
                source_work_id="sw_001",
                character_id="char_001",
                claim_type=ClaimType.PERSONALITY,
                content="Lin Shuang observes before acting.",
                status=ClaimStatus.VERIFIED,
                confidence=0.95,
                reasoning="source-backed",
                created_by="test",
            )
        )
        EvidenceRefRepository(session).add(
            EvidenceRef(
                id="evidence_001",
                claim_id="claim_001",
                chunk_id="chunk_001",
                excerpt="Lin Shuang observes before acting.",
                support_score=0.95,
            )
        )
        PersonaVersionRepository(session).add(
            PersonaVersion(
                id="pv_001",
                source_work_id="sw_001",
                character_id="char_001",
                version_number=1,
                core_self="Lin Shuang is careful.",
                speech_rules=["Speak with restraint."],
                behavior_rules=["Observe before acting."],
                world_adaptation_rules=["Can speak with real users."],
                forbidden_rules=["Do not rewrite source events."],
                source_claim_ids=["claim_001"],
            )
        )
        user = create_user(session, display_name="Test User", user_id="user_001").user
        conversation = create_conversation(
            session,
            user_id=user.id,
            character_id="char_001",
            persona_version_id="pv_001",
            conversation_id="conv_001",
        ).conversation
        ConversationRepository(session).update_summary(
            conversation.id,
            summary=summary,
            updated_at=utc_now(),
        )

        context = build_context_package(
            session,
            conversation_id=conversation.id,
            user_message="Continue with what we know.",
        ).context_package
        character = CharacterRepository(session).require("char_001")
        persona = PersonaVersionRepository(session).require("pv_001")
        claims = CanonClaimRepository(session).list_by_character("char_001")
        evidence = EvidenceRefRepository(session).list_by_claim("claim_001")
        session.commit()

    summary_section = _prompt_section(context.assembled_prompt, "# Conversation Summary")
    canon_section = _prompt_section(context.assembled_prompt, "# Verified Canon Claims")
    source_section = _prompt_section(context.assembled_prompt, "# Retrieved Source Chunks")
    assert "boundary: relationship continuity notes only; do not rewrite canon or persona." in (
        summary_section
    )
    assert "boundary: operational notes only; not source evidence, canon claims, or persona fields." in (
        summary_section
    )
    assert "private drafting ritual" in summary_section
    assert "Watch for attempts" in summary_section
    assert context.claim_ids == ["claim_001"]
    assert context.retrieved_chunk_ids == ["chunk_001"]
    assert "private drafting ritual" not in canon_section
    assert "Watch for attempts" not in source_section
    assert character.canonical_name == "Lin Shuang"
    assert persona.core_self == "Lin Shuang is careful."
    assert persona.speech_rules == ["Speak with restraint."]
    assert persona.source_claim_ids == ["claim_001"]
    assert [(claim.id, claim.content, claim.status) for claim in claims] == [
        ("claim_001", "Lin Shuang observes before acting.", ClaimStatus.VERIFIED)
    ]
    assert [(ref.id, ref.excerpt, ref.chunk_id) for ref in evidence] == [
        ("evidence_001", "Lin Shuang observes before acting.", "chunk_001")
    ]


def test_build_context_package_renders_legacy_summary_as_short_term_scene_state() -> None:
    prompt, _, _ = _build_context_for_summary("Legacy unlayered summary.")

    summary_section = _prompt_section(prompt, "# Conversation Summary")
    assert (
        "## short_term_scene_state\n"
        "boundary: temporary runtime context only; not canon, persona, or long-term memory.\n"
        "Legacy unlayered summary."
    ) in summary_section
    assert (
        "## user_memory_candidates\n"
        "boundary: unverified candidates only; not accepted user or relationship memories.\n"
        "- none"
    ) in summary_section
    assert (
        "## relationship_memory_notes\n"
        "boundary: relationship continuity notes only; do not rewrite canon or persona.\n"
        "- none"
    ) in summary_section
    assert (
        "## reflective_notes\n"
        "boundary: operational notes only; not source evidence, canon claims, or persona fields.\n"
        "- none"
    ) in summary_section


def test_build_context_package_renders_empty_summary_layers_with_none_state() -> None:
    prompt, _, _ = _build_context_for_summary(None)

    summary_section = _prompt_section(prompt, "# Conversation Summary")
    assert (
        "## short_term_scene_state\n"
        "boundary: temporary runtime context only; not canon, persona, or long-term memory.\n"
        "none"
    ) in summary_section
    assert (
        "## user_memory_candidates\n"
        "boundary: unverified candidates only; not accepted user or relationship memories.\n"
        "- none"
    ) in summary_section
    assert (
        "## relationship_memory_notes\n"
        "boundary: relationship continuity notes only; do not rewrite canon or persona.\n"
        "- none"
    ) in summary_section
    assert (
        "## reflective_notes\n"
        "boundary: operational notes only; not source evidence, canon claims, or persona fields.\n"
        "- none"
    ) in summary_section


def _build_context_for_summary(
    summary: str | None,
    *,
    accepted_memory_content: str | None = None,
) -> tuple[str, list[str], list[Memory]]:
    engine = create_database_engine("sqlite:///:memory:")
    create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        SourceWorkRepository(session).add(
            SourceWork(id="sw_001", title="Sample Work", source_type="markdown")
        )
        create_character(
            session,
            source_work_id="sw_001",
            canonical_name="Lin Shuang",
            character_id="char_001",
        )
        PersonaVersionRepository(session).add(
            PersonaVersion(
                id="pv_001",
                source_work_id="sw_001",
                character_id="char_001",
                version_number=1,
                core_self="Lin Shuang is observant and careful.",
            )
        )
        user = create_user(session, display_name="Test User", user_id="user_001").user
        conversation = create_conversation(
            session,
            user_id=user.id,
            character_id="char_001",
            persona_version_id="pv_001",
            conversation_id="conv_001",
        ).conversation
        if accepted_memory_content is not None:
            MemoryRepository(session).add(
                Memory(
                    id="mem_001",
                    user_id=user.id,
                    character_id="char_001",
                    conversation_id=conversation.id,
                    scope=MemoryScope.USER_MEMORY,
                    status=MemoryStatus.ACCEPTED,
                    content=accepted_memory_content,
                    importance=0.7,
                    reason="Accepted fixture memory.",
                )
            )
        if summary is not None:
            ConversationRepository(session).update_summary(
                conversation.id,
                summary=summary,
                updated_at=utc_now(),
            )

        context = build_context_package(
            session,
            conversation_id=conversation.id,
            user_message="I want to continue the scene.",
        ).context_package
        memories = MemoryRepository(session).list_for_user_character(user.id, "char_001")
        session.commit()

    return context.assembled_prompt, context.memory_ids, memories


def _prompt_section(prompt: str, heading: str) -> str:
    lines = prompt.splitlines()
    start = lines.index(heading) + 1
    end = next(
        (
            index
            for index, line in enumerate(lines[start:], start=start)
            if line.startswith("# ")
        ),
        len(lines),
    )
    return "\n".join(lines[start:end]).strip()

