# Task 02 Prompt: Correlation Error Envelope Foundation

Follow `VIBE_CODING_GUIDE.md`,
`plans/batch_07_api_write_foundation/BATCH_07_API_WRITE_FOUNDATION.md`, and
`plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/api-correlation-foundation
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task can start immediately and can run in parallel with Task 01.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `plans/batch_07_api_write_foundation/BATCH_07_API_WRITE_FOUNDATION.md`
- `plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`
- `src/personality_jelly/api/errors.py`
- `src/personality_jelly/api/schemas.py`
- `src/personality_jelly/api/dependencies.py`
- `src/personality_jelly/application/`
- `src/personality_jelly/llm/tracing.py`
- `tests/test_api_*.py`

## Goal

Add request/workflow correlation foundations for future write routes without adding middleware,
workflow-run tables, LLM trace columns, or provider-backed route behavior.

## Implementation Requirements

- Define transport-neutral application models for correlation input/results, such as:
  - request ID;
  - workflow ID;
  - workflow type;
  - status;
  - related IDs.
- Add API helper logic for normalizing `X-Request-ID` and optional body `request_id` for future
  write routes.
- Generate bounded server request IDs when the caller does not provide one.
- Reject blank, oversized, or mismatched header/body request IDs.
- Add response helpers or schemas for write responses that include `request_id`, `workflow_id`,
  `workflow_type`, `status`, IDs, and warnings.
- Extend or document the existing error envelope path so validation/provider/partial-persistence
  errors can include sanitized correlation details without overloading `trace_id`.
- Keep existing Batch 05 read-only error behavior compatible unless a test proves a safe additive
  field is needed.

## Expected Write Scope

Likely files:

- `src/personality_jelly/application/` correlation models/helpers;
- `src/personality_jelly/api/schemas.py`;
- `src/personality_jelly/api/errors.py`;
- focused API/application tests.

Avoid migrations, trace schema changes, request middleware, and provider call-site changes.

## Non-Goals

- Do not add workflow-run/link tables, LLM trace columns, audit persistence, idempotency tables, or
  request middleware.
- Do not add write routes in this task.
- Do not change provider-backed workflows.
- Do not add external observability frameworks.

## Verification

Run focused tests covering request ID generation/validation, header/body mismatch, response schema,
and sanitized error correlation.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `feature/api-correlation-foundation`, push the branch to
`origin`, and do not merge back to `dev`.

Final report should include:

- correlation model and helpers;
- error-envelope behavior;
- tests run;
- deferred schema/correlation work.
