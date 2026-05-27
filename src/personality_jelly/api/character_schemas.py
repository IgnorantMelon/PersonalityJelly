from __future__ import annotations

from typing import Any

from pydantic import Field

from personality_jelly.api.schemas import WriteRequestIdBody, WriteResponseEnvelope
from personality_jelly.application import (
    AuditActorType,
    CharacterCreateRequest,
    CharacterCreateResult as ApplicationCharacterCreateResult,
    CharacterIdentity,
    CorrelationContext,
    LocalActorContext,
)
from personality_jelly.application.correlation import MAX_CORRELATION_ID_LENGTH
from personality_jelly.application.inspection import InspectionModel


class CharacterCreateActor(InspectionModel):
    actor_type: AuditActorType = AuditActorType.API_USER
    actor_id: str = Field(min_length=1, max_length=MAX_CORRELATION_ID_LENGTH)
    actor_label: str | None = Field(default=None, max_length=MAX_CORRELATION_ID_LENGTH)
    user_id: str | None = Field(default=None, max_length=MAX_CORRELATION_ID_LENGTH)
    operation_reason: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_application_context(self) -> LocalActorContext:
        return LocalActorContext(
            actor_type=self.actor_type,
            actor_id=self.actor_id,
            actor_label=self.actor_label,
            user_id=self.user_id,
            operation_reason=self.operation_reason,
            metadata=self.metadata,
        )


class CharacterCreateRequestBody(WriteRequestIdBody):
    source_work_id: str = Field(min_length=1, max_length=128)
    canonical_name: str = Field(min_length=1, max_length=255)
    aliases: list[str] = Field(default_factory=list)
    character_id: str | None = Field(default=None, min_length=1, max_length=128)
    actor: CharacterCreateActor
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_application_request(
        self,
        correlation: CorrelationContext,
    ) -> CharacterCreateRequest:
        return CharacterCreateRequest(
            source_work_id=self.source_work_id,
            canonical_name=self.canonical_name,
            aliases=self.aliases,
            character_id=self.character_id,
            actor=self.actor.to_application_context(),
            correlation=correlation,
            metadata=self.metadata,
        )


class CharacterCreateResponseResult(InspectionModel):
    character: CharacterIdentity
    audit_event: dict[str, Any] | None = None


class CharacterCreateResponse(WriteResponseEnvelope):
    result: CharacterCreateResponseResult

    @classmethod
    def from_application_result(
        cls,
        result: ApplicationCharacterCreateResult,
    ) -> "CharacterCreateResponse":
        return cls(
            request_id=result.request_id,
            workflow_id=result.workflow_id,
            workflow_type=result.workflow_type,
            status=result.status,
            ids=result.ids,
            warnings=result.warnings,
            result=CharacterCreateResponseResult(
                character=result.character,
                audit_event=result.audit_event.model_dump(mode="json"),
            ),
        )
