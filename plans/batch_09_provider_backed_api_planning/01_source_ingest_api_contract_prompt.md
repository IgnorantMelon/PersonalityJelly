# Task 01 Prompt: Source Ingest API Contract

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_09_provider_backed_api_planning/BATCH_09_PROVIDER_BACKED_API_PLANNING.md`.

## Branch

Start from clean `dev`:

```powershell
git switch dev
git status --short --branch
git switch -c planning/api-source-ingest-contract
```

## Scheduling

This task can run in parallel with Task 02. It does not depend on any Batch 09 branch.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `plans/batch_08_api_workflow_persistence/BATCH_08_CLOSEOUT.md`
- `plans/batch_06_api_write_readiness/01_write_workflow_boundary_design.md`
- source ingestion modules and tests under `src/personality_jelly/ingestion`,
  `src/personality_jelly/application`, `src/personality_jelly/storage`, and `tests/`.

## Goal

Write an implementation-ready contract for exposing source ingest through a future HTTP write
workflow without implementing the route in this task.

## Output

Create:

- `plans/batch_09_provider_backed_api_planning/01_source_ingest_api_contract.md`

## Requirements

The contract must specify:

- candidate route names and method, such as `POST /source-works` or `POST /source-ingestions`;
- accepted input forms for TXT/Markdown content or file references, with local-path exposure rules;
- request fields, response fields, IDs, status codes, and error codes;
- source work/chunk persistence boundary and transaction policy;
- audit event operation, actor expectations, related IDs, and same-transaction expectations;
- workflow run type, workflow links, persisted IDs, and inspection/debugging expectations;
- idempotency key behavior, replay payload, request hash fields, and conflict behavior;
- redaction behavior for source text, source previews, local paths, secrets, and diagnostics;
- provider failure behavior if the workflow remains deterministic in the first implementation;
- focused storage/application/API tests needed by the implementation batch;
- explicit non-goals and deferred decisions.

## Non-Goals

- Do not implement the route.
- Do not call providers.
- Do not change ingestion behavior or storage schema.
- Do not add auth/workspace/platform features, file upload infrastructure, CORS, deployment, UI, or
  queues.

## Verification

Run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this planning artifact on `planning/api-source-ingest-contract`, push the branch to
`origin`, and do not merge back to `dev`.

Final report should include the route recommendation, chosen transaction/idempotency policy, tests
recommended for implementation, and deferred decisions.
