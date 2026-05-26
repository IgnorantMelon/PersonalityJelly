# Task 06 Prompt: Batch 08 Closeout Verification

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_08_api_workflow_persistence/BATCH_08_API_WORKFLOW_PERSISTENCE.md`.

## Branch

Start from the latest clean `dev` after Tasks 01-05 have been merged by a coordinator and create:

```powershell
git switch dev
git status --short --branch
git switch -c chore/batch-08-workflow-persistence-closeout
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task starts only after Tasks 01-05 are complete and merged into `dev` in dependency order.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `plans/batch_08_api_workflow_persistence/BATCH_08_API_WORKFLOW_PERSISTENCE.md`
- all completed Batch 08 task outputs or merged implementation commits;
- `plans/batch_07_api_write_foundation/BATCH_07_CLOSEOUT.md`;
- relevant storage/application/API tests.

## Goal

Verify Batch 08 closeout, confirm the workflow persistence foundation remains inside accepted
scope, and update project status docs.

## Verification Requirements

- Confirm no provider-backed write route was added.
- Confirm the existing deterministic write route set still works:
  - `POST /conversations`;
  - `POST /memories/{memory_id}/review`;
  - `PATCH /memories/{memory_id}`;
  - `POST /memories/{memory_id}/archive`.
- Confirm audit events persist in the same transaction as deterministic domain mutations.
- Confirm workflow runs and links persist for deterministic write workflows.
- Confirm LLM trace correlation migration fields or link behavior exists for future provider-backed
  diagnostics.
- Confirm idempotency replay returns stored results without duplicating domain/audit/workflow rows.
- Confirm idempotency conflicts return sanitized `409 conflict` responses.
- Confirm provider failure and partial-persistence contracts include request/workflow correlation,
  persisted IDs, trace IDs, retry hints, and redacted details.
- Confirm audit/workflow inspection routes are read-only, filterable, stable-ordered, and redacted.
- Confirm API handlers remain thin adapters over `personality_jelly.application`.
- Run focused storage/application/API tests for Batch 08.
- Run full pytest.

## Expected Write Scope

Likely files:

- `plans/batch_08_api_workflow_persistence/BATCH_08_API_WORKFLOW_PERSISTENCE.md` closeout note;
- `README.md` status update;
- `VIBE_CODING_GUIDE.md` status update;
- optional closeout report under this directory if useful.

Avoid source changes except small test or docs corrections needed to close the batch.

## Non-Goals

- Do not add source ingest, character/persona setup, turn execution, summary, benchmark, or other
  provider-backed write workflows during closeout.
- Do not add auth/workspace/platform features, deployment, CORS, UI, queues, or external
  observability.
- Do not migrate unrelated read-only route pagination during closeout.

## Completion

Commit only closeout changes on `chore/batch-08-workflow-persistence-closeout`, push the branch to
`origin`, and do not merge back to `dev`.

Final report should include:

- Batch 08 acceptance summary;
- schema and route set verified;
- tests run;
- docs updated;
- next recommended batch or blockers.
