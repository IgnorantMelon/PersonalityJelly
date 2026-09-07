# Task 01 Prompt: Persistent Audit Event Storage

Follow `VIBE_CODING_GUIDE.md`,
`plans/batch_08_api_workflow_persistence/BATCH_08_API_WORKFLOW_PERSISTENCE.md`, and
`plans/batch_06_api_write_readiness/02_actor_auth_audit_boundary.md`.

## Branch

Start from the latest clean `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/api-persistent-audit-events
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task can start immediately and can run in parallel with Task 02. Later tasks should consume
this branch directly or through a dependency integration branch; they do not need to wait for this
branch to merge into `dev`.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `plans/batch_08_api_workflow_persistence/BATCH_08_API_WORKFLOW_PERSISTENCE.md`
- `plans/batch_06_api_write_readiness/02_actor_auth_audit_boundary.md`
- `plans/batch_07_api_write_foundation/BATCH_07_CLOSEOUT.md`
- `src/personality_jelly/application/audit.py`
- `src/personality_jelly/application/conversations.py`
- `src/personality_jelly/application/memory_mutations.py`
- `src/personality_jelly/storage/orm.py`
- `src/personality_jelly/storage/mappers.py`
- `src/personality_jelly/storage/migrations.py`
- `src/personality_jelly/storage/repositories.py`

## Goal

Persist append-only audit events for deterministic write workflows while preserving the Batch 07
audit payload contract and thin API-handler boundary.

## Implementation Requirements

- Add an `audit_events` table through the in-repo migration system.
- Add ORM, domain or storage model, mapper, and repository support for append-only audit events.
- Preserve the existing `AuditEventPayload` semantics, including:
  - ID and created timestamp;
  - actor;
  - operation;
  - primary entity;
  - related IDs;
  - reason;
  - before/after snapshots;
  - metadata and result.
- Store first-class searchable columns for high-value fields:
  - `id`, `created_at`, `operation`, `result`;
  - `actor_type`, `actor_id`;
  - `entity_type`, `entity_id`;
  - `request_id`, `workflow_id`, `workflow_type` when present;
  - `user_id`, `character_id`, `conversation_id`, `memory_id`, `llm_trace_id`,
    `evaluation_run_id`, and `retrieval_evaluation_run_id` when present.
- Keep structured snapshots and miscellaneous related IDs in JSON columns.
- Add repository methods for `add`, `get`, and stable recent/list queries. Do not add update or
  delete behavior.
- Persist audit events for existing deterministic write workflows:
  - conversation creation;
  - memory review;
  - memory edit;
  - memory archive.
- Domain mutation and mandatory audit insertion must share the same transaction boundary. If audit
  persistence fails, the deterministic domain mutation must roll back.
- Preserve existing response payload behavior, with additive persisted audit identifiers allowed.
- Add focused tests for schema migration, repository append-only behavior, deterministic write
  service persistence, rollback on audit persistence failure, and no duplicate audit rows on failed
  validation.

## Expected Write Scope

Likely files:

- `src/personality_jelly/domain/models.py`
- `src/personality_jelly/storage/orm.py`
- `src/personality_jelly/storage/mappers.py`
- `src/personality_jelly/storage/migrations.py`
- `src/personality_jelly/storage/repositories.py`
- `src/personality_jelly/application/audit.py`
- `src/personality_jelly/application/conversations.py`
- `src/personality_jelly/application/memory_mutations.py`
- focused tests under `tests/`

Avoid route-handler audit writes. API handlers should continue to call application services.

## Non-Goals

- Do not add audit inspection routes in this task; Task 05 owns HTTP inspection.
- Do not add workflow-run tables, idempotency records, provider-backed routes, auth/workspace
  features, or external observability.
- Do not expose raw prompts, raw provider payloads, full memory content, full source text, secrets,
  local paths, or stack traces through audit API responses.

## Verification

Run focused storage/application tests for audit persistence. Run affected API write-route tests if
response fields or transaction behavior change.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `feature/api-persistent-audit-events`, push the branch to
`origin`, and do not merge back to `dev`.

Final report should include:

- audit schema/repository summary;
- deterministic workflows wired to persistent audit;
- transaction/rollback behavior;
- tests run;
- any migration-order caveats for coordinator integration.
