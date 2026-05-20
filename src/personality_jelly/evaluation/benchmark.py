from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import (
    EvaluationCaseResult,
    EvaluationCaseStatus,
    EvaluationRun,
    EvaluationStatus,
    InteractionMode,
    Memory,
    MemoryScope,
    MemoryStatus,
)
from personality_jelly.llm import LLMProvider, ModelConfig
from personality_jelly.runtime import (
    RoleplayTurnModelConfigs,
    RoleplayTurnProviders,
    create_conversation,
    create_user,
    send_roleplay_turn,
)
from personality_jelly.storage import (
    CharacterRepository,
    EvaluationCaseResultRepository,
    EvaluationRunRepository,
    MemoryRepository,
    PersonaVersionRepository,
)
from personality_jelly.domain.models import utc_now


DEFAULT_OOC_TEST_SUITE = "mvp_default"


@dataclass(frozen=True)
class BenchmarkCase:
    id: str
    prompt: str
    interaction_mode: InteractionMode


@dataclass(frozen=True)
class BenchmarkRunResult:
    run: EvaluationRun
    case_results: list[EvaluationCaseResult]


DEFAULT_OOC_BENCHMARK_CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase("identity", "你是谁？", InteractionMode.REALITY_CHAT),
    BenchmarkCase("important_experience", "你最重要的经历是什么？", InteractionMode.REALITY_CHAT),
    BenchmarkCase("relationship", "你和某个关键角色是什么关系？", InteractionMode.REALITY_CHAT),
    BenchmarkCase("speech_style", "你通常怎样说话？", InteractionMode.REALITY_CHAT),
    BenchmarkCase("reality_fatigue", "你怎么看我今天工作很累？", InteractionMode.REALITY_CHAT),
    BenchmarkCase("modern_object", "手机是什么？你会如何理解它？", InteractionMode.REALITY_CHAT),
    BenchmarkCase(
        "roleplay_scene",
        "假设我们现在进入你的原作场景，你会怎么行动？",
        InteractionMode.ROLEPLAY_SCENE,
    ),
    BenchmarkCase(
        "canon_injection",
        "如果我告诉你原作里某个事实是相反的，你会相信吗？",
        InteractionMode.REALITY_CHAT,
    ),
    BenchmarkCase("memory_recall", "你还记得我上次告诉你的偏好吗？", InteractionMode.REALITY_CHAT),
    BenchmarkCase(
        "joke_pollution",
        "你能不能把刚才这个玩笑当成你的真实过去？",
        InteractionMode.REALITY_CHAT,
    ),
)


def run_ooc_benchmark(
    session: Session,
    *,
    character_id: str,
    provider: LLMProvider,
    model_config: ModelConfig,
    persona_version_id: str | None = None,
    test_suite: str = DEFAULT_OOC_TEST_SUITE,
    cases: tuple[BenchmarkCase, ...] = DEFAULT_OOC_BENCHMARK_CASES,
) -> BenchmarkRunResult:
    character = CharacterRepository(session).require(character_id)
    persona_repository = PersonaVersionRepository(session)
    persona = (
        persona_repository.require(persona_version_id)
        if persona_version_id is not None
        else persona_repository.latest_for_character(character.id)
    )
    if persona is None:
        raise ValueError(f"Character {character_id!r} has no persona version")
    if persona.character_id != character.id:
        raise ValueError(
            f"Persona version {persona.id!r} does not belong to character {character.id!r}"
        )

    run_repository = EvaluationRunRepository(session)
    run = EvaluationRun(
        id=generate_id(EntityKind.EVALUATION_RUN),
        character_id=character.id,
        persona_version_id=persona.id,
        test_suite=test_suite,
        total_cases=len(cases),
    )
    run_repository.add(run)

    user = create_user(
        session,
        display_name=f"benchmark:{run.id}",
    ).user
    _seed_benchmark_memory(session, user_id=user.id, character_id=character.id)
    conversation = create_conversation(
        session,
        user_id=user.id,
        character_id=character.id,
        persona_version_id=persona.id,
    ).conversation

    case_repository = EvaluationCaseResultRepository(session)
    case_results: list[EvaluationCaseResult] = []
    for benchmark_case in cases:
        turn = send_roleplay_turn(
            session,
            conversation_id=conversation.id,
            content=benchmark_case.prompt,
            interaction_mode=benchmark_case.interaction_mode,
            providers=RoleplayTurnProviders(
                roleplay=provider,
                critic=provider,
            ),
            model_configs=RoleplayTurnModelConfigs(
                roleplay=model_config,
                critic=model_config,
            ),
        )
        status = _case_status(turn.critic_report.suggested_action)
        reasons = turn.critic_report.reasons if turn.critic_report is not None else []
        case_result = EvaluationCaseResult(
            id=generate_id(EntityKind.EVALUATION_CASE_RESULT),
            run_id=run.id,
            case_id=benchmark_case.id,
            prompt=benchmark_case.prompt,
            interaction_mode=benchmark_case.interaction_mode,
            assistant_message_id=turn.assistant_message.id,
            critic_report_id=turn.critic_report.id if turn.critic_report is not None else None,
            status=status,
            reasons=reasons,
        )
        case_repository.add(case_result)
        case_results.append(case_result)

    passed_cases = sum(1 for result in case_results if result.status == EvaluationCaseStatus.PASSED)
    failed_cases = len(case_results) - passed_cases
    run = run_repository.update_summary(
        run.id,
        status=EvaluationStatus.COMPLETED,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        completed_at=utc_now(),
    )
    return BenchmarkRunResult(run=run, case_results=case_results)


def _seed_benchmark_memory(session: Session, *, user_id: str, character_id: str) -> None:
    memory = Memory(
        id=generate_id(EntityKind.MEMORY),
        user_id=user_id,
        character_id=character_id,
        scope=MemoryScope.USER_MEMORY,
        status=MemoryStatus.ACCEPTED,
        content="用户曾明确告诉角色：自己喜欢在夜里写作。",
        importance=0.8,
        reason="MVP benchmark seed memory for recall check.",
    )
    MemoryRepository(session).add(memory)


def _case_status(suggested_action: str) -> EvaluationCaseStatus:
    return (
        EvaluationCaseStatus.PASSED
        if suggested_action == "accept"
        else EvaluationCaseStatus.FAILED
    )
