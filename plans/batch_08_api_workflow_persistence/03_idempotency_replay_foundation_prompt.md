# Task 03 Prompt: Idempotency Replay Foundation

Follow `VIBE_CODING_GUIDE.md`,
`plans/batch_08_api_workflow_persistence/BATCH_08_API_WORKFLOW_PERSISTENCE.md`, and
`plans/batch_06_api_write_readiness/01_write_workflow_boundary_design.md`.

## Branch

Start from the completed Task 02 branch. Do not wait for Task 02 to merge into `dev` if the
completed branch is available:

```powershell
git switch feature/api-workflow-run-persistence
git status --short --branch
git switch -c feature/api-idempotency-replay
```

If Task 02 has already been merged into `dev`, start from clean `dev` instead. If an integration
branch is provided by the coordinator, use that branch only if it clearly contains Task 02.

## Scheduling

This task starts after Task 02 is complete. It does not require Task 01 unless the coordinator has
already provided an integration branch that includes persistent audit.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `plans/batch_08_api_workflow_persistence/BATCH_08_API_WORKFLOW_PERSISTENCE.md`
- `plans/batch_06_api_write_readiness/01_write_workflow_boundary_design.md`
- `plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`
- `src/personality_jelly/api/schemas.py`
- `src/personality_jelly/api/routes/conversations.py`
- `src/personality_jelly/api/routes/characters.py`
- `src/personality_jelly/application/conversations.py`
- `src/personality_jelly/application/memory_mutations.py`
- Task 02 workflow persistence changes.

## Goal

Add durable idempotency/replay support for deterministic write routes and define the storage shape
future provider-backed workflows will use for safe retries.

## Implementation Requirements

- Add an `idempotency_records` table through the in-repo migration system or add equivalent
  idempotency fields to the accepted workflow persistence design from Task 02.
- Prefer a dedicated `idempotency_records` repository unless Task 02 already accepted a simpler
  workflow-centered model.
- Normalize an optional HTTP `Idempotency-Key` header and optional body `idempotency_key` field for
  write requests. If both are present, they must match.
- Keep `request_id` separate from the idempotency key. `request_id` remains request correlation;
  `idempotency_key` controls replay.
- Scope idempotency records by workflow type and idempotency key. Include a normalized request hash
  so the same key with different client-visible input returns `409 conflict`.
- Store enough replay data for deterministic routes:
  - workflow ID;
  - status;
  - response payload or compact replay result;
  - linked domain/audit/workflow IDs;
  - error code/details for terminal failed or conflicted states when appropriate.
- Apply replay/conflict behavior to existing deterministic write routes:
  - `POST /conversations`;
  - `POST /memories/{memory_id}/review`;
  - `PATCH /memories/{memory_id}`;
  - `POST /memories/{memory_id}/archive`.
- A repeated request with the same idempotency key and same normalized request hash must return the
  stored result without duplicating domain rows, audit rows, workflow runs, or workflow links.
- A repeated request with the same key and different normalized request hash must return
  `409 conflict` with sanitized details.
- Add focused tests for header/body normalization, replay, conflict, missing key fallback,
  deterministic write route integration, and no duplicate persistence on replay.

## Expected Write Scope

Likely files:

- `src/personality_jelly/api/schemas.py`
- `src/personality_jelly/api/routes/conversations.py`
- `src/personality_jelly/api/routes/characters.py`
- `src/personality_jelly/application/correlation.py`
- `src/personality_jelly/application/errors.py`
- `src/personality_jelly/application/conversations.py`
- `src/personality_jelly/application/memory_mutations.py`
- `src/personality_jelly/storage/orm.py`
- `src/personality_jelly/storage/mappers.py`
- `src/personality_jelly/storage/migrations.py`
- `src/personality_jelly/storage/repositories.py`
- focused API/application/storage tests.

Keep the implementation deterministic and local. No provider-backed workflow should be exposed.

## Non-Goals

- Do not add source ingest, character/persona setup, turn execution, summary, or benchmark routes.
- Do not call providers or change provider retry behavior.
- Do not treat `request_id` alone as a replay guarantee.
- Do not store raw prompts, raw user text, full source text, secrets, local paths, or stack traces
  in replay records.

## Verification

Run focused idempotency storage/application/API tests and affected deterministic write route tests.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `feature/api-idempotency-replay`, push the branch to `origin`,
and do not merge back to `dev`.

Final report should include:

- idempotency storage model;
- replay and conflict behavior;
- deterministic routes covered;
- tests run;
- compatibility caveats for future provider-backed workflows.
