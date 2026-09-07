# Task 02 Prompt: Workflow Run And Correlation Persistence

Follow `VIBE_CODING_GUIDE.md`,
`plans/batch_08_api_workflow_persistence/BATCH_08_API_WORKFLOW_PERSISTENCE.md`, and
`plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`.

## Branch

Start from the latest clean `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/api-workflow-run-persistence
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task can start immediately and can run in parallel with Task 01. Task 03 should branch from
this completed task branch rather than waiting for it to merge into `dev`.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `plans/batch_08_api_workflow_persistence/BATCH_08_API_WORKFLOW_PERSISTENCE.md`
- `plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`
- `src/personality_jelly/application/correlation.py`
- `src/personality_jelly/application/conversations.py`
- `src/personality_jelly/application/memory_mutations.py`
- `src/personality_jelly/llm/tracing.py`
- `src/personality_jelly/storage/orm.py`
- `src/personality_jelly/storage/mappers.py`
- `src/personality_jelly/storage/migrations.py`
- `src/personality_jelly/storage/repositories.py`

## Goal

Add durable workflow-run and workflow-link persistence so request/workflow/domain/trace correlation
can be inspected before provider-backed write routes are exposed.

## Implementation Requirements

- Add `workflow_runs` and `workflow_run_links` tables through the in-repo migration system.
- Add request/workflow correlation fields to `llm_raw_outputs` using the accepted hybrid model:
  - `request_id`;
  - `workflow_id`;
  - `workflow_step`;
  - optional `related_ids` JSON if it fits existing mapper conventions.
- Add ORM, domain or storage models, mappers, and repositories for workflow runs and workflow links.
- Workflow runs should store at least:
  - `workflow_id`;
  - `request_id`;
  - `workflow_type`;
  - `status`;
  - `started_at`;
  - `completed_at`;
  - normalized error code/details when failed;
  - warnings and persisted IDs as redaction-safe JSON.
- Workflow links should associate a workflow with durable records such as conversations, memories,
  audit events, messages, context packages, failure cases, eval runs, retrieval eval runs, and LLM
  traces.
- Add application helpers to start, complete, fail, and link workflow runs without importing API
  modules.
- Persist workflow runs and links for existing deterministic write workflows:
  - conversation creation;
  - memory review;
  - memory edit;
  - memory archive.
- Preserve existing response fields. Additive persisted workflow metadata is allowed when tests
  cover compatibility.
- Add focused tests for migration, repository behavior, workflow status transitions, link creation,
  deterministic write service wiring, and LLM raw output correlation fields.

## Expected Write Scope

Likely files:

- `src/personality_jelly/domain/models.py`
- `src/personality_jelly/application/correlation.py`
- `src/personality_jelly/storage/orm.py`
- `src/personality_jelly/storage/mappers.py`
- `src/personality_jelly/storage/migrations.py`
- `src/personality_jelly/storage/repositories.py`
- `src/personality_jelly/llm/tracing.py`
- `src/personality_jelly/application/conversations.py`
- `src/personality_jelly/application/memory_mutations.py`
- focused tests under `tests/`

Keep workflow persistence transport-neutral. API routes should not write workflow rows directly.

## Non-Goals

- Do not add idempotency/replay behavior in this task; Task 03 owns it.
- Do not add persistent audit storage unless needed only as an optional workflow link target; Task
  01 owns audit persistence.
- Do not add provider-backed routes or change provider call semantics.
- Do not migrate every domain table to carry workflow columns.

## Verification

Run focused storage/application tests for workflow persistence. Run affected API write-route tests
if response behavior changes.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `feature/api-workflow-run-persistence`, push the branch to
`origin`, and do not merge back to `dev`.

Final report should include:

- workflow schema/repository summary;
- deterministic workflows wired to workflow persistence;
- LLM trace correlation changes;
- tests run;
- migration-order caveats for Task 03 and coordinator integration.
