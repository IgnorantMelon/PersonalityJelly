# Task 04 Prompt: Conversation Creation Write Route

Follow `VIBE_CODING_GUIDE.md`,
`plans/batch_07_api_write_foundation/BATCH_07_API_WRITE_FOUNDATION.md`, and
`plans/batch_06_api_write_readiness/01_write_workflow_boundary_design.md`.

## Branch

Start from the latest `dev` after Tasks 01-03 are merged and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/api-conversation-create
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task depends on Tasks 01, 02, and 03. It can run in parallel with Task 05 after those
foundations are merged.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `plans/batch_07_api_write_foundation/BATCH_07_API_WRITE_FOUNDATION.md`
- `plans/batch_06_api_write_readiness/01_write_workflow_boundary_design.md`
- `plans/batch_06_api_write_readiness/02_actor_auth_audit_boundary.md`
- `plans/batch_06_api_write_readiness/03_api_redaction_policy.md`
- `plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`
- `src/personality_jelly/api/app.py`
- `src/personality_jelly/api/routes/`
- `src/personality_jelly/api/schemas.py`
- `src/personality_jelly/application/`
- `src/personality_jelly/runtime/`
- `src/personality_jelly/storage/repositories.py`
- `tests/test_api_*.py`

## Goal

Implement a deterministic local-first conversation creation write workflow through an application
service and a thin FastAPI adapter.

## Implementation Requirements

- Add an application service for conversation creation that:
  - accepts explicit `user_id`, `character_id`, and optional `persona_version_id` when appropriate;
  - accepts local actor context;
  - accepts request/workflow correlation context;
  - validates required IDs through repositories;
  - creates the conversation in one transaction;
  - returns a structured result with conversation ID, related IDs, correlation IDs, status, and
    payload-only audit metadata if the actor/audit foundation provides it.
- Add a thin HTTP route, likely `POST /conversations`, that:
  - validates request body;
  - acquires a session;
  - calls the application service;
  - returns the safe write-era response shape;
  - maps validation, not-found, conflict, and unexpected errors through the shared error envelope.
- Apply default redaction to the response.
- Add route and application tests for success, missing IDs, validation failures, actor/correlation
  behavior, and no provider invocation.

## Expected Write Scope

Likely files:

- `src/personality_jelly/application/` write service module;
- `src/personality_jelly/api/routes/conversations.py` or adjacent route module;
- `src/personality_jelly/api/schemas.py`;
- focused API/application tests.

Avoid CLI behavior changes unless the new application service is intentionally shared.

## Non-Goals

- Do not implement turn execution, first-message generation, summary generation, provider calls, or
  memory mutation.
- Do not add auth, workspace, persistent audit, idempotency persistence, or workflow-run tables.
- Do not change read-only conversation inspection response behavior.

## Verification

Run focused conversation creation API/application tests and any existing conversation route tests
that the change touches.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `feature/api-conversation-create`, push the branch to `origin`,
and do not merge back to `dev`.

Final report should include:

- route and application service contract;
- transaction/error behavior;
- tests run;
- deferred workflows.
