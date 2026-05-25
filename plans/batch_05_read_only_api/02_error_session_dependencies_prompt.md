# Task 02 Prompt: Error And Session Dependencies

Follow `VIBE_CODING_GUIDE.md` and `plans/batch_05_read_only_api/BATCH_05_READ_ONLY_API.md`.

## Goal

Add shared API dependencies and exception handling so route tasks can stay thin and consistent.

## Scope

- Add a request/session dependency that yields SQLAlchemy sessions from app-owned database
  resources.
- Ensure read-only requests close sessions cleanly and roll back on exceptions.
- Add `ErrorEnvelope` / `ErrorBody` response models.
- Register exception handlers for lookup errors, value errors, FastAPI request validation errors,
  and unexpected errors.
- Add tests for `404 not_found`, `422 validation_error`, and `500 unexpected_error` envelope
  shapes.

## Non-Goals

- Do not add auth, actor, workspace, or permission dependencies.
- Do not add provider dependencies or provider error mapping in this read-only batch.
- Do not change `personality_jelly.application.normalize_error` semantics unless route error
  mapping cannot be implemented without a small extension.
- Do not add write transaction helpers yet.

## Implementation Notes

- Keep HTTP-specific models in `personality_jelly.api`, not in `application`.
- Preserve the envelope fields: `code`, `message`, `details`, and optional `trace_id`.
- Route handlers should be able to depend on one `Session` and call application services directly.
- FastAPI validation errors should retain useful field details without leaking stack traces.

## Verification

Run focused API error/session tests. If shared bootstrap code changes, also run application
bootstrap tests.

## Completion

Commit only this task's changes on `feature/api-errors-sessions`.

Do not merge this branch back into `dev`. Push only the task branch to `origin` and report the
branch name and commit hash. A coordinator or maintainer will handle review and integration into
`dev`.
