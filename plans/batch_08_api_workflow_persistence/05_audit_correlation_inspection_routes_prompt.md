# Task 05 Prompt: Audit And Workflow Inspection Routes

Follow `VIBE_CODING_GUIDE.md`,
`plans/batch_08_api_workflow_persistence/BATCH_08_API_WORKFLOW_PERSISTENCE.md`,
`plans/batch_06_api_write_readiness/03_api_redaction_policy.md`, and
`plans/batch_06_api_write_readiness/04_pagination_filter_contract.md`.

## Branch

Start from a dependency integration branch that combines Task 01 and Task 02. The recommended
coordinator flow is:

```powershell
git switch feature/api-workflow-run-persistence
git status --short --branch
git switch -c integration/batch-08-inspection-deps
git merge --no-ff feature/api-persistent-audit-events
git switch -c feature/api-audit-workflow-inspection
```

If the coordinator already created `integration/batch-08-inspection-deps`, branch from that. If all
dependencies are already merged into `dev`, start from clean `dev`.

## Scheduling

This task starts after Tasks 01 and 02 are complete. It can run while Task 03/04 continue because it
only exposes audit and workflow inspection, not idempotency record inspection.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `plans/batch_08_api_workflow_persistence/BATCH_08_API_WORKFLOW_PERSISTENCE.md`
- `plans/batch_06_api_write_readiness/03_api_redaction_policy.md`
- `plans/batch_06_api_write_readiness/04_pagination_filter_contract.md`
- `src/personality_jelly/application/inspection.py`
- `src/personality_jelly/api/inspection.py`
- `src/personality_jelly/api/routes/diagnostics.py`
- `src/personality_jelly/api/routes/characters.py`
- Task 01 persistent audit changes.
- Task 02 workflow persistence changes.

## Goal

Expose redaction-aware local read-only inspection for persisted audit events and workflow runs so
Batch 08 foundations are debuggable without exposing provider-backed writes.

## Implementation Requirements

- Add application inspection models/services for audit events and workflow runs.
- Add read-only API routes, using existing route conventions:
  - `GET /audit-events`;
  - `GET /audit-events/{audit_event_id}`;
  - `GET /workflow-runs`;
  - `GET /workflow-runs/{workflow_id}`.
- List routes should use accepted limit and exact-match filter conventions:
  - default `limit=50`;
  - maximum `limit=200`;
  - no offset pagination;
  - stable descending `created_at`/`started_at` ordering with deterministic ID tie-breakers;
  - exact filters such as `request_id`, `workflow_id`, `workflow_type`, `operation`,
    `actor_id`, `entity_type`, `entity_id`, `status`, `user_id`, `character_id`, and
    `conversation_id` where repository support exists.
- Detail routes should return 404 through the existing error envelope when a record is missing.
- Default responses must be redaction-aware. Do not expose raw prompts, raw provider payloads, full
  memory content, full source text, secrets, local paths, or stack traces.
- Add OpenAPI contract tests for the new read-only routes.
- Add route tests for list/detail success, filters, limit validation, not-found behavior, and
  redaction.
- Keep route handlers as thin adapters over application inspection services.

## Expected Write Scope

Likely files:

- `src/personality_jelly/application/inspection.py`
- `src/personality_jelly/api/routes/diagnostics.py` or a new focused route module if consistent
  with existing API registration style;
- `src/personality_jelly/api/app.py`
- `src/personality_jelly/api/redaction.py`
- `tests/test_api_contract.py`
- focused API/application tests.

Avoid exposing idempotency record listing in this task; replay records may contain response hashes
and stored payloads that need a separate exposure decision.

## Non-Goals

- Do not add write routes.
- Do not expose provider-backed workflows.
- Do not add auth/workspace/platform features.
- Do not migrate all existing Batch 05 list endpoints to cursor pagination.
- Do not expose raw diagnostic payloads just because they are associated with audit/workflow IDs.

## Verification

Run focused API/application inspection tests and the OpenAPI contract test.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `feature/api-audit-workflow-inspection`, push the branch to
`origin`, and do not merge back to `dev`.

Final report should include:

- route set added;
- filters and ordering behavior;
- redaction guarantees;
- tests run;
- deferred inspection surfaces.
