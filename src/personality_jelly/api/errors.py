from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from personality_jelly.application import (
    ErrorCorrelation,
    NormalizedError,
    dump_error_correlation,
    normalize_error,
)


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorBody


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(LookupError, _handle_lookup_error)
    app.add_exception_handler(ValueError, _handle_value_error)
    app.add_exception_handler(RequestValidationError, _handle_request_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)


async def _handle_lookup_error(request: Request, exc: LookupError) -> JSONResponse:
    return _error_response(normalize_error(exc), status_code=404)


async def _handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    return _error_response(normalize_error(exc), status_code=422)


async def _handle_request_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    normalized = NormalizedError(
        code="validation_error",
        message="Request validation failed",
        details={"errors": _validation_error_details(exc.errors())},
    )
    return _error_response(normalized, status_code=422)


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(normalize_error(exc), status_code=500)


def build_error_envelope(
    error: NormalizedError,
    *,
    correlation: ErrorCorrelation | None = None,
    trace_id: str | None = None,
) -> ErrorEnvelope:
    return ErrorEnvelope(
        error=ErrorBody(
            code=error.code,
            message=error.message,
            details=with_error_correlation(error.details, correlation=correlation),
            trace_id=trace_id,
        )
    )


def with_error_correlation(
    details: dict[str, Any] | None = None,
    *,
    correlation: ErrorCorrelation | None = None,
) -> dict[str, Any]:
    merged = dict(details or {})
    if correlation is not None:
        merged["correlation"] = dump_error_correlation(correlation)
    return merged


def _error_response(error: NormalizedError, *, status_code: int) -> JSONResponse:
    envelope = build_error_envelope(error)
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json"),
    )


def _validation_error_details(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for error in errors:
        details.append(
            {
                "loc": list(error.get("loc", [])),
                "msg": str(error.get("msg", "")),
                "type": str(error.get("type", "")),
            }
        )
    return details
