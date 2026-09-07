from __future__ import annotations

from typing import Any

from pydantic import Field

from personality_jelly.api.schemas import WriteRequestIdBody
from personality_jelly.application import (
    AuditActorType,
    LocalActorContext,
    MemoryReviewDecision,
)
from personality_jelly.application.inspection import InspectionModel


class MemoryMutationActorBody(InspectionModel):
    actor_type: AuditActorType
    actor_id: str = Field(min_length=1)
    actor_label: str | None = None
    user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_application_actor(self, *, operation_reason: str | None) -> LocalActorContext:
        return LocalActorContext(
            actor_type=self.actor_type,
            actor_id=self.actor_id,
            actor_label=self.actor_label,
            user_id=self.user_id,
            operation_reason=operation_reason,
            metadata=self.metadata,
        )


class MemoryMutationBaseBody(WriteRequestIdBody):
    actor: MemoryMutationActorBody | None = None
    reason: str | None = None
    user_id: str | None = None
    character_id: str | None = None
    conversation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryReviewRequestBody(MemoryMutationBaseBody):
    decision: MemoryReviewDecision


class MemoryEditRequestBody(MemoryMutationBaseBody):
    content: str | None = None


class MemoryArchiveRequestBody(MemoryMutationBaseBody):
    pass
