from __future__ import annotations

from typing import Any

from pydantic import Field

from personality_jelly.application import (
    CorrelationContext,
    WorkflowContext,
    WorkflowRelatedIds,
    WorkflowResponseSummary,
    WorkflowStatus,
    WorkflowWarning,
    build_workflow_response,
    generate_request_id,
)
from personality_jelly.application.correlation import MAX_CORRELATION_ID_LENGTH
from personality_jelly.application.inspection import InspectionModel

REQUEST_ID_HEADER = "X-Request-ID"


class WriteRequestCorrelation(InspectionModel):
    request_id: str = Field(min_length=1, max_length=MAX_CORRELATION_ID_LENGTH)

    def to_application_context(self) -> CorrelationContext:
        return CorrelationContext(request_id=self.request_id)


class WriteRequestIdBody(InspectionModel):
    request_id: str | None = Field(default=None, max_length=MAX_CORRELATION_ID_LENGTH)


class WriteResponseEnvelope(WorkflowResponseSummary):
    result: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_workflow(
        cls,
        workflow: WorkflowContext,
        *,
        status: WorkflowStatus | str = WorkflowStatus.COMPLETED,
        ids: WorkflowRelatedIds | None = None,
        warnings: list[WorkflowWarning] | None = None,
        result: dict[str, Any] | None = None,
    ) -> "WriteResponseEnvelope":
        summary = build_workflow_response(
            workflow,
            status=status,
            ids=ids,
            warnings=warnings,
        )
        return cls(
            **summary.model_dump(mode="python"),
            result=result or {},
        )


def resolve_write_request_correlation(
    *,
    header_request_id: object | None = None,
    body_request_id: object | None = None,
) -> WriteRequestCorrelation:
    normalized_header = _normalize_optional_request_id(
        header_request_id,
        source=REQUEST_ID_HEADER,
    )
    normalized_body = _normalize_optional_request_id(
        body_request_id,
        source="body request_id",
    )

    if normalized_header is not None and normalized_body is not None:
        if normalized_header != normalized_body:
            raise ValueError(f"{REQUEST_ID_HEADER} and body request_id must match")
        return WriteRequestCorrelation(request_id=normalized_header)

    return WriteRequestCorrelation(
        request_id=normalized_header or normalized_body or generate_request_id()
    )


def _normalize_optional_request_id(value: object | None, *, source: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{source} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{source} must not be blank")
    if len(normalized) > MAX_CORRELATION_ID_LENGTH:
        raise ValueError(
            f"{source} must be at most {MAX_CORRELATION_ID_LENGTH} characters"
        )
    return normalized
