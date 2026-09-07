from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import Field, field_validator

from personality_jelly.api.schemas import WriteRequestIdBody, WriteResponseEnvelope
from personality_jelly.application import (
    AuditActorType,
    CharacterPersonaSetupCounts,
    CharacterPersonaSetupPersistedIds,
    CharacterPersonaSetupRedactionFlags,
    CharacterPersonaSetupWorkflowRequest,
    CharacterPersonaSetupWorkflowResult,
    CorrelationContext,
    IdempotencyContext,
    LocalActorContext,
    PersonaSetupModelRoleBundle,
    PersonaSetupProviderRoleBundle,
)
from personality_jelly.application.correlation import MAX_CORRELATION_ID_LENGTH
from personality_jelly.application.inspection import InspectionModel


_MODEL_LABEL_MAX_LENGTH = 128
_WINDOWS_PATH_PATTERN = re.compile(r"^[a-zA-Z]:[\\/].+")
_POSIX_PATH_PATTERN = re.compile(
    r"^/(?:Users|home|var|tmp|etc|opt|mnt|Volumes|private|data|root|workspace|projects)/.+"
)
_URL_PATTERN = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_SECRET_PATTERN = re.compile(
    r"(?:\bBearer\s+|\bsk-[A-Za-z0-9_-]{10,}|\bapi[_-]?key\b|\btoken\b|\bsecret\b)",
    re.IGNORECASE,
)


class PersonaSetupActor(InspectionModel):
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


class PersonaSetupProviderRoleModel(InspectionModel):
    model: str | None = Field(default=None, max_length=_MODEL_LABEL_MAX_LENGTH)

    @field_validator("model", mode="before")
    @classmethod
    def _normalize_model_label(cls, value: object) -> object:
        return _normalize_optional_model_label(value, field_name="provider role model")


class PersonaSetupProviderRoles(InspectionModel):
    reader: PersonaSetupProviderRoleModel | None = None
    verifier: PersonaSetupProviderRoleModel | None = None
    persona_compiler: PersonaSetupProviderRoleModel | None = None

    def model_labels(self) -> dict[str, str | None]:
        return {
            "reader": self.reader.model if self.reader is not None else None,
            "verifier": self.verifier.model if self.verifier is not None else None,
            "persona_compiler": (
                self.persona_compiler.model if self.persona_compiler is not None else None
            ),
        }


class PersonaSetupProviderRequest(InspectionModel):
    source: Literal["stub", "env"]
    model: str | None = Field(default=None, max_length=_MODEL_LABEL_MAX_LENGTH)
    roles: PersonaSetupProviderRoles = Field(default_factory=PersonaSetupProviderRoles)

    @field_validator("model", mode="before")
    @classmethod
    def _normalize_bundle_model(cls, value: object) -> object:
        return _normalize_optional_model_label(value, field_name="provider model")


class PersonaSetupWorkflowOptions(InspectionModel):
    max_chunks: int | None = Field(default=None, ge=1)


class PersonaSetupRunRequestBody(WriteRequestIdBody):
    source_work_id: str = Field(min_length=1, max_length=128)
    character_id: str | None = Field(default=None, min_length=1, max_length=128)
    provider: PersonaSetupProviderRequest
    workflow_options: PersonaSetupWorkflowOptions = Field(
        default_factory=PersonaSetupWorkflowOptions
    )
    actor: PersonaSetupActor
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_work_id", "character_id", mode="before")
    @classmethod
    def _normalize_ids(cls, value: object) -> object:
        if value is None or not isinstance(value, str):
            return value
        return value.strip()

    def validate_path_character_id(self, character_id: str) -> None:
        if self.character_id is not None and self.character_id != character_id:
            raise ValueError("path character_id and body character_id must match")

    def idempotency_payload(self, *, character_id: str) -> dict[str, Any]:
        payload = self.model_dump(
            mode="json",
            exclude={"request_id", "idempotency_key", "character_id"},
        )
        payload["character_id"] = character_id
        return payload

    def to_application_request(
        self,
        *,
        character_id: str,
        correlation: CorrelationContext,
        idempotency: IdempotencyContext,
        provider_roles: PersonaSetupProviderRoleBundle,
        model_roles: PersonaSetupModelRoleBundle,
    ) -> CharacterPersonaSetupWorkflowRequest:
        return CharacterPersonaSetupWorkflowRequest(
            source_work_id=self.source_work_id,
            character_id=character_id,
            provider_roles=provider_roles,
            model_roles=model_roles,
            actor=self.actor.to_application_context(),
            correlation=correlation,
            idempotency=idempotency,
            max_chunks=self.workflow_options.max_chunks,
            metadata=self.metadata,
        )


class PersonaSetupRunResponseResult(InspectionModel):
    persisted_ids: CharacterPersonaSetupPersistedIds
    counts: CharacterPersonaSetupCounts
    redaction: CharacterPersonaSetupRedactionFlags


class PersonaSetupRunResponse(WriteResponseEnvelope):
    result: PersonaSetupRunResponseResult

    @classmethod
    def from_application_result(
        cls,
        result: CharacterPersonaSetupWorkflowResult,
    ) -> "PersonaSetupRunResponse":
        return cls(
            request_id=result.request_id,
            workflow_id=result.workflow_id,
            workflow_type=result.workflow_type,
            status=result.status,
            ids=result.ids,
            warnings=result.warnings,
            result=PersonaSetupRunResponseResult(
                persisted_ids=result.persisted_ids,
                counts=result.counts,
                redaction=result.redaction,
            ),
        )


def _normalize_optional_model_label(value: object, *, field_name: str) -> object:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > _MODEL_LABEL_MAX_LENGTH:
        raise ValueError(f"{field_name} must be at most {_MODEL_LABEL_MAX_LENGTH} characters")
    if _WINDOWS_PATH_PATTERN.match(normalized) or _POSIX_PATH_PATTERN.match(normalized):
        raise ValueError(f"{field_name} must not contain local paths")
    if _URL_PATTERN.match(normalized):
        raise ValueError(f"{field_name} must not contain URLs")
    if _SECRET_PATTERN.search(normalized):
        raise ValueError(f"{field_name} must not contain secrets")
    return normalized
