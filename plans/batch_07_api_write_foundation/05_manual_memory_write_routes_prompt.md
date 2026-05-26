# Task 05 Prompt: Manual Memory Write Routes

Follow `VIBE_CODING_GUIDE.md`,
`plans/batch_07_api_write_foundation/BATCH_07_API_WRITE_FOUNDATION.md`, and
`plans/batch_06_api_write_readiness/01_write_workflow_boundary_design.md`.

## Branch

Start from the latest `dev` after Tasks 01-03 are merged and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/api-memory-mutations
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task depends on Tasks 01, 02, and 03. It can run in parallel with Task 04 after those
foundations are merged.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `plans/batch_07_api_write_foundation/BATCH_07_API_WRITE_FOUNDATION.md`
- `plans/batch_06_api_write_readiness/01_write_workflow_boundary_design.md`
- `plans/batch_06_api_write_readiness/02_actor_auth_audit_boundary.md`
- `plans/batch_06_api_write_readiness/03_api_redaction_policy.md`
- `plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`
- `src/personality_jelly/application/audit.py`
- `src/personality_jelly/application/`
- `src/personality_jelly/memory/`
- `src/personality_jelly/storage/repositories.py`
- `src/personality_jelly/api/routes/`
- `tests/test_api_*.py`

## Goal

Implement deterministic manual memory review/edit/archive write workflows through application
services and thin FastAPI adapters.

## Implementation Requirements

- Add application services for:
  - manual memory review;
  - manual memory edit;
  - manual memory archive.
- Require explicit local actor context and caller reason for every memory mutation.
- Validate memory ownership and related IDs before mutation.
- Preserve memory/canon boundaries; manual memory changes must never rewrite source canon.
- Return structured results with updated memory summaries, request/workflow correlation IDs, status,
  and payload-only audit metadata.
- Apply default redaction to memory content/reason fields in broad default responses, while allowing
  explicit local debug behavior only if Task 01 provides it.
- Add thin HTTP adapters with explicit route paths chosen by this task and documented in tests.
- Add route/application tests for success, not-found, actor missing, reason missing, invalid status
  transition, redaction, and audit payload behavior.

## Expected Write Scope

Likely files:

- `src/personality_jelly/application/` memory write service module;
- `src/personality_jelly/api/routes/` memory route module;
- `src/personality_jelly/api/schemas.py`;
- focused API/application tests.

Avoid broad memory curator/guard behavior changes unless strictly needed for manual service wiring.

## Non-Goals

- Do not run Memory Curator or Memory Guard as part of manual review/edit/archive routes.
- Do not add automatic memory extraction, provider calls, or semantic judgment changes.
- Do not add persistent audit storage, auth/workspace features, or idempotency persistence.
- Do not mutate canon claims or source evidence.

## Verification

Run focused manual memory write API/application tests and any existing memory route tests touched by
the change.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `feature/api-memory-mutations`, push the branch to `origin`, and
do not merge back to `dev`.

Final report should include:

- route paths and service contracts;
- actor/reason/audit behavior;
- redaction behavior;
- tests run;
- deferred automatic/provider-backed memory work.
