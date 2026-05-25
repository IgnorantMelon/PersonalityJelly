from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from personality_jelly.application import (
    CharacterDetail,
    CharacterSummary,
    ClaimSummary,
    ContextPackageDetail,
    EvaluationRunDetail,
    EvaluationRunSummary,
    EvidenceRefSummary,
    ExpansionState,
    InspectionListResult,
    LayeredSummary,
    MemorySummary,
    MessageSummary,
    OOCBenchmarkDiagnostics,
    PersonaVersionSummary,
    SourceChunkDetail,
    SourceChunkSummary,
    SourceWorkSummary,
)
from personality_jelly.domain import (
    ClaimStatus,
    ClaimType,
    EvaluationStatus,
    InteractionMode,
    MemoryScope,
    MemoryStatus,
    MessageRole,
)


NOW = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)


def test_summary_models_serialize_enums_and_datetimes() -> None:
    summary = CharacterSummary(
        id="char_001",
        source_work_id="sw_001",
        canonical_name="Lin Shuang",
        aliases=["A-Shuang"],
        created_at=NOW,
        latest_persona_version_id="persona_001",
        claim_count=3,
    )

    payload = summary.model_dump(mode="json")

    assert payload == {
        "id": "char_001",
        "source_work_id": "sw_001",
        "canonical_name": "Lin Shuang",
        "aliases": ["A-Shuang"],
        "created_at": "2026-05-25T12:00:00Z",
        "latest_persona_version_id": "persona_001",
        "claim_count": 3,
    }


def test_detail_models_keep_ids_and_optional_expansions_separate() -> None:
    source_work = SourceWorkSummary(
        id="sw_001",
        title="Novel",
        language="zh-CN",
        source_type="markdown",
        created_at=NOW,
    )
    persona = PersonaVersionSummary(
        id="persona_001",
        character_id="char_001",
        source_work_id="sw_001",
        version_number=1,
        source_claim_ids=["claim_001"],
        created_at=NOW,
    )
    detail = CharacterDetail(
        id="char_001",
        source_work_id="sw_001",
        canonical_name="Lin Shuang",
        created_at=NOW,
        source_work=source_work,
        latest_persona_version=persona,
        claims=[
            ClaimSummary(
                id="claim_001",
                source_work_id="sw_001",
                character_id="char_001",
                claim_type=ClaimType.PERSONALITY,
                status=ClaimStatus.VERIFIED,
                confidence=0.9,
                content="Lin Shuang observes before acting.",
                created_by="reader",
                evidence_ids=["evidence_001"],
            )
        ],
    )

    payload = detail.model_dump(mode="json")

    assert payload["source_work_id"] == "sw_001"
    assert payload["source_work"]["id"] == "sw_001"
    assert payload["latest_persona_version"]["id"] == "persona_001"
    assert payload["claims"][0]["claim_type"] == "personality"
    assert payload["claims"][0]["status"] == "verified"


def test_context_package_detail_records_expansion_convention() -> None:
    context = ContextPackageDetail(
        id="ctx_001",
        conversation_id="conv_001",
        interaction_mode=InteractionMode.REALITY_CHAT,
        persona_version_id="persona_001",
        claim_ids=["claim_001"],
        memory_ids=["mem_001"],
        retrieved_chunk_ids=["chunk_001"],
        created_at=NOW,
        expansion=ExpansionState(mode="detail", expanded=["claims", "memories"]),
        assembled_prompt="prompt",
        retrieved_chunks=[
            SourceChunkSummary(
                id="chunk_001",
                source_work_id="sw_001",
                paragraph_index=1,
                text_preview="Lin Shuang observes...",
            )
        ],
        memories=[
            MemorySummary(
                id="mem_001",
                user_id="user_001",
                character_id="char_001",
                conversation_id="conv_001",
                scope=MemoryScope.USER_MEMORY,
                status=MemoryStatus.ACCEPTED,
                content="User likes writing at night.",
                importance=0.8,
                reason="User stated preference.",
                created_at=NOW,
            )
        ],
    )

    payload = context.model_dump(mode="json")

    assert payload["claim_ids"] == ["claim_001"]
    assert payload["expansion"]["mode"] == "detail"
    assert payload["memories"][0]["scope"] == "user_memory"
    assert payload["retrieved_chunks"][0]["text_preview"] == "Lin Shuang observes..."


def test_layered_summary_and_messages_support_conversation_detail() -> None:
    message = MessageSummary(
        id="msg_001",
        conversation_id="conv_001",
        role=MessageRole.USER,
        content="Hello",
        created_at=NOW,
    )
    layers = LayeredSummary(
        short_term_scene_state="none",
        user_memory_candidates=["candidate"],
        relationship_memory_notes=["note"],
        reflective_notes=["reflect"],
    )

    assert message.model_dump(mode="json")["role"] == "user"
    assert layers.model_dump(mode="json")["relationship_memory_notes"] == ["note"]


def test_benchmark_detail_carries_diagnostics() -> None:
    run = EvaluationRunDetail(
        id="eval_001",
        character_id="char_001",
        persona_version_id="persona_001",
        test_suite="mvp_default",
        status=EvaluationStatus.COMPLETED,
        total_cases=2,
        passed_cases=1,
        failed_cases=1,
        created_at=NOW,
        diagnostics=OOCBenchmarkDiagnostics(
            total_cases=2,
            passed_cases=1,
            failed_cases=1,
            pass_rate=0.5,
        ),
    )

    payload = run.model_dump(mode="json")

    assert payload["status"] == "completed"
    assert payload["diagnostics"]["pass_rate"] == 0.5
    assert payload["cases"] == []


def test_models_are_strict_and_frozen() -> None:
    summary = SourceChunkDetail(
        id="chunk_001",
        source_work_id="sw_001",
        paragraph_index=1,
        text="full text",
    )

    with pytest.raises(ValidationError):
        SourceChunkDetail(
            id="chunk_001",
            source_work_id="sw_001",
            paragraph_index=1,
            text="full text",
            unknown=True,
        )

    with pytest.raises(ValidationError):
        summary.paragraph_index = 2


def test_list_result_wraps_transport_neutral_items() -> None:
    result = InspectionListResult(
        items=[
            CharacterSummary(
                id="char_001",
                source_work_id="sw_001",
                canonical_name="Lin Shuang",
                created_at=NOW,
            )
        ],
        total_count=1,
        limit=20,
    )

    payload = result.model_dump(mode="json")

    assert payload["items"][0]["id"] == "char_001"
    assert payload["total_count"] == 1
    assert payload["limit"] == 20
