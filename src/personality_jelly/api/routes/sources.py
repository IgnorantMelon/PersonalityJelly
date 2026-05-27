from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from personality_jelly.api.dependencies import get_write_session
from personality_jelly.api.errors import build_error_envelope
from personality_jelly.api.redaction import redact_payload
from personality_jelly.api.schemas import (
    IDEMPOTENCY_KEY_HEADER,
    REQUEST_ID_HEADER,
    resolve_write_request_correlation,
    resolve_write_request_idempotency,
)
from personality_jelly.api.source_schemas import (
    SourceWorkIngestRequestBody,
    SourceWorkIngestResponse,
)
from personality_jelly.application import (
    SOURCE_WORK_INGEST_SUCCESS_STATUS_CODE,
    SOURCE_WORK_INGEST_WORKFLOW_TYPE,
    ConflictError,
    CorrelationContext,
    IdempotencyContext,
    NormalizedError,
    WorkflowStatus,
    build_error_correlation,
    build_idempotency_context,
    ingest_source_work_workflow,
    load_idempotency_replay,
    normalize_error,
)

router = APIRouter(tags=["sources"])


@router.post(
    "/source-works",
    response_model=SourceWorkIngestResponse,
    status_code=SOURCE_WORK_INGEST_SUCCESS_STATUS_CODE,
)
def post_source_work(
    request: SourceWorkIngestRequestBody,
    session: Annotated[Session, Depends(get_write_session)],
    header_request_id: Annotated[str | None, Header(alias=REQUEST_ID_HEADER)] = None,
    header_idempotency_key: Annotated[
        str | None,
        Header(alias=IDEMPOTENCY_KEY_HEADER),
    ] = None,
) -> SourceWorkIngestResponse | JSONResponse:
    correlation: CorrelationContext | None = None
    try:
        write_correlation = resolve_write_request_correlation(
            header_request_id=header_request_id,
            body_request_id=request.request_id,
        )
        correlation = write_correlation.to_application_context()
        idempotency = _required_source_ingest_idempotency_context(
            request,
            header_idempotency_key=header_idempotency_key,
        )
        replay = load_idempotency_replay(session, idempotency)
        if replay is not None:
            return JSONResponse(
                status_code=replay.response_status_code,
                content=replay.replay_payload,
            )

        result = ingest_source_work_workflow(
            session,
            request.to_application_request(correlation),
            idempotency=idempotency,
        )
    except Exception as error:
        return _source_ingest_error_response(error, correlation=correlation)

    return SourceWorkIngestResponse.model_validate(
        redact_payload(SourceWorkIngestResponse.from_application_result(result))
    )


def _required_source_ingest_idempotency_context(
    request: SourceWorkIngestRequestBody,
    *,
    header_idempotency_key: object | None,
) -> IdempotencyContext:
    idempotency_key = resolve_write_request_idempotency(
        header_idempotency_key=header_idempotency_key,
        body_idempotency_key=request.idempotency_key,
    )
    if idempotency_key is None:
        raise ValueError(f"{IDEMPOTENCY_KEY_HEADER} is required")

    return build_idempotency_context(
        workflow_type=SOURCE_WORK_INGEST_WORKFLOW_TYPE,
        idempotency_key=idempotency_key,
        request_payload=request.model_dump(
            mode="json",
            exclude={"request_id", "idempotency_key"},
        ),
    )


def _source_ingest_error_response(
    error: Exception,
    *,
    correlation: CorrelationContext | None,
) -> JSONResponse:
    status_code = _status_code_for_error(error)
    error_correlation = (
        build_error_correlation(
            correlation,
            status=WorkflowStatus.FAILED,
            failed_step=SOURCE_WORK_INGEST_WORKFLOW_TYPE,
        )
        if correlation is not None
        else None
    )
    envelope = build_error_envelope(
        _normalize_source_ingest_error(error),
        correlation=error_correlation,
    )
    return JSONResponse(
        status_code=status_code,
        content=redact_payload(envelope),
    )


def _status_code_for_error(error: Exception) -> int:
    if isinstance(error, ConflictError):
        return 409
    if isinstance(error, ValueError):
        return 422
    if isinstance(error, ValidationError):
        return 422
    return 500


def _normalize_source_ingest_error(error: Exception) -> NormalizedError:
    if not isinstance(error, ValidationError):
        return normalize_error(error)
    details = []
    for item in error.errors(include_input=False, include_context=False):
        details.append(
            {
                "loc": list(item.get("loc", [])),
                "msg": str(item.get("msg", "")),
                "type": str(item.get("type", "")),
            }
        )
    message = details[0]["msg"] if details else "Request validation failed"
    if message.startswith("Value error, "):
        message = message.removeprefix("Value error, ")
    return NormalizedError(
        code="validation_error",
        message=message,
        details={"errors": details},
    )
