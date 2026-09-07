from __future__ import annotations

from dataclasses import dataclass

from pydantic import Field
from sqlalchemy.orm import Session

from personality_jelly.application.inspection import InspectionModel
from personality_jelly.application.providers import ModelRoleBundle, ProviderRoleBundle
from personality_jelly.domain import CriticAction, InteractionMode, MemoryStatus
from personality_jelly.runtime import RoleplayTurnOrchestrationResult, send_roleplay_turn


class TurnMemorySummary(InspectionModel):
    id: str
    scope: str
    status: MemoryStatus


class TurnWorkflowSummary(InspectionModel):
    conversation_id: str
    user_message_id: str
    assistant_message_id: str
    context_package_id: str
    interaction_mode: InteractionMode
    critic_report_id: str | None = None
    critic_action: CriticAction | None = None
    retry_count: int = Field(ge=0)
    rejected_assistant_message_id: str | None = None
    rejected_critic_report_id: str | None = None
    failure_case_ids: list[str] = Field(default_factory=list)
    memories: list[TurnMemorySummary] = Field(default_factory=list)

    @property
    def memory_ids(self) -> list[str]:
        return [memory.id for memory in self.memories]


@dataclass(frozen=True)
class TurnWorkflowResult:
    summary: TurnWorkflowSummary
    runtime_result: RoleplayTurnOrchestrationResult


def run_turn_workflow(
    session: Session,
    *,
    conversation_id: str,
    content: str,
    provider_roles: ProviderRoleBundle,
    model_roles: ModelRoleBundle,
    interaction_mode: InteractionMode | None = None,
    retry_on_critic: bool = False,
) -> TurnWorkflowResult:
    runtime_result = send_roleplay_turn(
        session,
        conversation_id=conversation_id,
        content=content,
        providers=provider_roles.to_runtime_turn_providers(),
        model_configs=model_roles.to_runtime_turn_model_configs(),
        interaction_mode=interaction_mode,
        retry_on_critic=retry_on_critic,
    )
    return TurnWorkflowResult(
        summary=_summarize_turn(runtime_result),
        runtime_result=runtime_result,
    )


def _summarize_turn(result: RoleplayTurnOrchestrationResult) -> TurnWorkflowSummary:
    return TurnWorkflowSummary(
        conversation_id=result.assistant_message.conversation_id,
        user_message_id=result.user_message.id,
        assistant_message_id=result.assistant_message.id,
        context_package_id=result.context_package.id,
        interaction_mode=result.context_package.interaction_mode,
        critic_report_id=result.critic_report.id if result.critic_report is not None else None,
        critic_action=(
            result.critic_report.suggested_action
            if result.critic_report is not None
            else None
        ),
        retry_count=result.retry_count,
        rejected_assistant_message_id=(
            result.rejected_assistant_message.id
            if result.rejected_assistant_message is not None
            else None
        ),
        rejected_critic_report_id=(
            result.rejected_critic_report.id
            if result.rejected_critic_report is not None
            else None
        ),
        failure_case_ids=[failure_case.id for failure_case in result.failure_cases],
        memories=[
            TurnMemorySummary(
                id=memory.id,
                scope=str(memory.scope),
                status=memory.status,
            )
            for memory in result.memories
        ],
    )
