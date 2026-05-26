from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ConflictError(RuntimeError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


@dataclass(frozen=True)
class NormalizedError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def normalize_error(error: Exception) -> NormalizedError:
    if isinstance(error, ConflictError):
        return NormalizedError(
            code="conflict",
            message=str(error),
            details=error.details,
        )
    if isinstance(error, LookupError):
        return NormalizedError(code="not_found", message=str(error))
    if isinstance(error, ValueError):
        return NormalizedError(code="validation_error", message=str(error))
    return NormalizedError(
        code="unexpected_error",
        message=str(error) or error.__class__.__name__,
        details={"exception_type": error.__class__.__name__},
    )
