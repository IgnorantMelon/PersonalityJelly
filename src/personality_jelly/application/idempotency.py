from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import Field
from sqlalchemy.orm import Session

from personality_jelly.application.correlation import (
    MAX_CORRELATION_ID_LENGTH,
    MAX_WORKFLOW_TYPE_LENGTH,
    WorkflowRelatedIds,
)
from personality_jelly.application.errors import ConflictError
from personality_jelly.application.inspection import InspectionModel
from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import IdempotencyRecord
from personality_jelly.domain.models import utc_now
from personality_jelly.storage import IdempotencyRecordRepository


MAX_IDEMPOTENCY_KEY_LENGTH = MAX_CORRELATION_ID_LENGTH
REQUEST_HASH_LENGTH = 64


class IdempotencyContext(InspectionModel):
    workflow_type: str = Field(min_length=1, max_length=MAX_WORKFLOW_TYPE_LENGTH)
    idempotency_key: str = Field(min_length=1, max_length=MAX_IDEMPOTENCY_KEY_LENGTH)
    request_hash: str = Field(min_length=REQUEST_HASH_LENGTH, max_length=REQUEST_HASH_LENGTH)


class IdempotencyReplay(InspectionModel):
    response_status_code: int = Field(ge=100, le=599)
    replay_payload: dict[str, Any]
    workflow_id: str
    request_id: str
    status: str
    related_ids: dict[str, Any] = Field(default_factory=dict)


def normalize_idempotency_key(
    value: object | None,
    *,
    source: str,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{source} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{source} must not be blank")
    if len(normalized) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise ValueError(
            f"{source} must be at most {MAX_IDEMPOTENCY_KEY_LENGTH} characters"
        )
    return normalized


def build_idempotency_request_hash(
    *,
    workflow_type: str,
    request_payload: Mapping[str, Any],
) -> str:
    normalized_payload = {
        "workflow_type": workflow_type,
        "request": _canonicalize(request_payload),
    }
    serialized = json.dumps(
        normalized_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_idempotency_context(
    *,
    workflow_type: str,
    idempotency_key: str | None,
    request_payload: Mapping[str, Any],
) -> IdempotencyContext | None:
    if idempotency_key is None:
        return None
    return IdempotencyContext(
        workflow_type=workflow_type,
        idempotency_key=idempotency_key,
        request_hash=build_idempotency_request_hash(
            workflow_type=workflow_type,
            request_payload=request_payload,
        ),
    )


def load_idempotency_replay(
    session: Session,
    context: IdempotencyContext | None,
) -> IdempotencyReplay | None:
    if context is None:
        return None
    record = IdempotencyRecordRepository(session).find_by_scope(
        workflow_type=context.workflow_type,
        idempotency_key=context.idempotency_key,
    )
    if record is None:
        return None
    if record.request_hash != context.request_hash:
        raise ConflictError(
            "Idempotency key was already used with different request input",
            details={
                "workflow_type": context.workflow_type,
                "idempotency_record_id": record.id,
                "conflict": "request_hash_mismatch",
            },
        )
    return IdempotencyReplay(
        response_status_code=record.response_status_code,
        replay_payload=record.replay_payload,
        workflow_id=record.workflow_id,
        request_id=record.request_id,
        status=record.status,
        related_ids=record.related_ids,
    )


def store_idempotency_replay(
    session: Session,
    context: IdempotencyContext | None,
    *,
    request_id: str,
    workflow_id: str,
    status: str,
    response_status_code: int,
    replay_payload: dict[str, Any],
    related_ids: WorkflowRelatedIds | Mapping[str, Any] | None = None,
    error_code: str | None = None,
    error_details: dict[str, Any] | None = None,
) -> IdempotencyRecord | None:
    if context is None:
        return None
    now = utc_now()
    related_payload = (
        related_ids.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
        if isinstance(related_ids, WorkflowRelatedIds)
        else dict(related_ids or {})
    )
    return IdempotencyRecordRepository(session).add(
        IdempotencyRecord(
            id=generate_id(EntityKind.IDEMPOTENCY_RECORD),
            workflow_type=context.workflow_type,
            idempotency_key=context.idempotency_key,
            request_hash=context.request_hash,
            request_id=request_id,
            workflow_id=workflow_id,
            status=status,
            response_status_code=response_status_code,
            replay_payload=replay_payload,
            related_ids=related_payload,
            error_code=error_code,
            error_details=error_details,
            created_at=now,
            updated_at=now,
        )
    )


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(field_value) for key, field_value in value.items()}
    if isinstance(value, list | tuple):
        return [_canonicalize(item) for item in value]
    return value
