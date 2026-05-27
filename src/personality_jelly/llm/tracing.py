from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError
from pydantic_core import ErrorDetails

from personality_jelly.core import EntityKind, generate_id
from personality_jelly.domain import LLMRawOutput
from personality_jelly.llm.provider import LLMProvider, ModelConfig


class LLMTraceRecorder(Protocol):
    def record(
        self,
        *,
        operation: str,
        schema_name: str,
        provider_name: str,
        model_name: str | None,
        request_id: str | None = None,
        workflow_id: str | None = None,
        workflow_step: str | None = None,
        related_ids: dict[str, Any] | None = None,
        response_schema: dict[str, Any],
        raw_output: str,
        parsed_output: dict[str, Any] | None,
        validation_errors: list[str],
    ) -> LLMRawOutput:
        """Persist one structured LLM operation trace."""


def record_structured_output(
    *,
    recorder: LLMTraceRecorder | None,
    operation: str,
    schema_name: str,
    provider: LLMProvider,
    model_config: ModelConfig,
    request_id: str | None = None,
    workflow_id: str | None = None,
    workflow_step: str | None = None,
    related_ids: Mapping[str, Any] | None = None,
    response_schema: dict[str, Any],
    raw_output: Mapping[str, Any],
    parsed_output: BaseModel | Mapping[str, Any] | None = None,
    validation_error: ValidationError | None = None,
) -> LLMRawOutput | None:
    if recorder is None:
        return None
    return recorder.record(
        operation=operation,
        schema_name=schema_name,
        provider_name=provider.name,
        model_name=model_config.model,
        request_id=request_id,
        workflow_id=workflow_id,
        workflow_step=workflow_step,
        related_ids=dict(related_ids) if related_ids is not None else None,
        response_schema=response_schema,
        raw_output=json.dumps(raw_output, ensure_ascii=False, sort_keys=True, default=str),
        parsed_output=_dump_parsed_output(parsed_output),
        validation_errors=_dump_validation_errors(validation_error),
    )


def _dump_parsed_output(parsed_output: BaseModel | Mapping[str, Any] | None) -> dict[str, Any] | None:
    if parsed_output is None:
        return None
    if isinstance(parsed_output, BaseModel):
        return parsed_output.model_dump(mode="json")
    return dict(parsed_output)


def _dump_validation_errors(error: ValidationError | None) -> list[str]:
    if error is None:
        return []
    return [
        json.dumps(
            _serializable_error(error_details),
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        for error_details in error.errors()
    ]


def _serializable_error(error_details: ErrorDetails) -> dict[str, Any]:
    return {key: value for key, value in dict(error_details).items() if key != "ctx"}


class RepositoryLLMTraceRecorder:
    def __init__(
        self,
        repository,
        *,
        request_id: str | None = None,
        workflow_id: str | None = None,
        workflow_step: str | None = None,
        related_ids: Mapping[str, Any] | None = None,
    ) -> None:
        self.repository = repository
        self.request_id = request_id
        self.workflow_id = workflow_id
        self.workflow_step = workflow_step
        self.related_ids = dict(related_ids) if related_ids is not None else None

    def record(
        self,
        *,
        operation: str,
        schema_name: str,
        provider_name: str,
        model_name: str | None,
        request_id: str | None = None,
        workflow_id: str | None = None,
        workflow_step: str | None = None,
        related_ids: dict[str, Any] | None = None,
        response_schema: dict[str, Any],
        raw_output: str,
        parsed_output: dict[str, Any] | None,
        validation_errors: list[str],
    ) -> LLMRawOutput:
        trace = LLMRawOutput(
            id=generate_id(EntityKind.LLM_RAW_OUTPUT),
            operation=operation,
            schema_name=schema_name,
            provider_name=provider_name,
            model_name=model_name,
            request_id=request_id or self.request_id,
            workflow_id=workflow_id or self.workflow_id,
            workflow_step=workflow_step or self.workflow_step,
            related_ids=related_ids or self.related_ids,
            response_schema=response_schema,
            raw_output=raw_output,
            parsed_output=parsed_output,
            validation_errors=validation_errors,
        )
        return self.repository.add(trace)

    def with_correlation(
        self,
        *,
        request_id: str,
        workflow_id: str,
        workflow_step: str | None = None,
        related_ids: Mapping[str, Any] | None = None,
    ) -> RepositoryLLMTraceRecorder:
        return RepositoryLLMTraceRecorder(
            self.repository,
            request_id=request_id,
            workflow_id=workflow_id,
            workflow_step=workflow_step,
            related_ids=related_ids,
        )
