# Task 04 Prompt: Provider Failure And Partial-Persistence Contracts

Follow `VIBE_CODING_GUIDE.md`,
`plans/batch_08_api_workflow_persistence/BATCH_08_API_WORKFLOW_PERSISTENCE.md`, and
`plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`.

## Branch

Start from a dependency integration branch that combines Task 01 and Task 03. The recommended
coordinator flow is:

```powershell
git switch feature/api-idempotency-replay
git status --short --branch
git switch -c integration/batch-08-failure-contracts-deps
git merge --no-ff feature/api-persistent-audit-events
git switch -c feature/api-provider-failure-contracts
```

If the coordinator already created `integration/batch-08-failure-contracts-deps`, branch from that.
If all dependencies are already merged into `dev`, start from clean `dev`.

## Scheduling

This task starts after Tasks 01, 02, and 03 are complete. It uses a dependency integration branch so
provider failure contracts can reference persistent audit, workflow runs, and idempotency behavior
without waiting for all dependencies to merge into `dev`.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `plans/batch_08_api_workflow_persistence/BATCH_08_API_WORKFLOW_PERSISTENCE.md`
- `plans/batch_06_api_write_readiness/01_write_workflow_boundary_design.md`
- `plans/batch_06_api_write_readiness/03_api_redaction_policy.md`
- `plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`
- `src/personality_jelly/application/errors.py`
- `src/personality_jelly/api/errors.py`
- `src/personality_jelly/application/correlation.py`
- Task 01 persistent audit changes.
- Task 03 idempotency changes.

## Goal

Add normalized, redaction-safe application/API contracts for provider failures, validation errors,
retry hints, and partial persistence before any provider-backed write route is exposed.

## Implementation Requirements

- Add application-level normalized error or result models for provider-backed workflow outcomes:
  - provider failure;
  - provider validation failure;
  - partial persistence;
  - retryable conflict;
  - guard/critic follow-up failure where applicable.
- Preserve the existing API error envelope compatibility path. Until a broader error migration is
  explicitly accepted, request/workflow correlation should remain under `details.correlation` and
  `trace_id` should refer only to a relevant LLM trace ID.
- Partial-persistence details should support:
  - `failed_step`;
  - `persisted_ids`;
  - `llm_trace_ids`;
  - `audit_event_ids`;
  - `workflow_id`;
  - `retry_hint`;
  - sanitized error family/code.
- Add helpers that future provider-backed services can use to mark workflow runs failed or partial,
  link persisted IDs, and record an audit event where persistence is mandatory.
- Ensure the contract never exposes raw prompts, assembled prompts, raw provider payloads, secrets,
  local paths, stack traces, full source chunks, or full memory content.
- Add tests for normalized errors, redaction of partial details, error-envelope compatibility, and
  workflow/audit/idempotency metadata shape.
- Do not add provider-backed write routes. Test helper behavior with direct application/unit tests
  and synthetic failures.

## Expected Write Scope

Likely files:

- `src/personality_jelly/application/errors.py`
- `src/personality_jelly/application/correlation.py`
- `src/personality_jelly/application/audit.py`
- `src/personality_jelly/api/errors.py`
- focused tests under `tests/`

Avoid touching provider prompts or route surfaces unless a small compatibility test requires an
additive error helper.

## Non-Goals

- Do not expose source ingest, character/persona setup, turn execution, summary generation, or
  benchmark execution through HTTP.
- Do not call providers or alter existing semantic workflows.
- Do not introduce external retry frameworks, queues, task runners, or observability services.
- Do not make partial persistence the default for deterministic local writes that can still roll
  back atomically.

## Verification

Run focused application/API error contract tests and redaction tests for partial details.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `feature/api-provider-failure-contracts`, push the branch to
`origin`, and do not merge back to `dev`.

Final report should include:

- normalized failure/partial models;
- error-envelope compatibility behavior;
- redaction guarantees;
- tests run;
- provider-backed work still deferred.
