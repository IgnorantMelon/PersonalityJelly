# Task 03 Prompt: Provider-Backed Write Contract Matrix

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_09_provider_backed_api_planning/BATCH_09_PROVIDER_BACKED_API_PLANNING.md`.

## Branch

Start from a dependency integration branch that combines Tasks 01 and 02:

```powershell
git switch planning/api-source-ingest-contract
git status --short --branch
git switch -c integration/batch-09-contracts
git merge --no-ff planning/api-character-persona-contract
git switch -c planning/api-provider-write-contract-matrix
```

If the coordinator already created `integration/batch-09-contracts`, branch from that.

## Scheduling

This task starts after Tasks 01 and 02 are complete.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- Batch 09 overview plan
- Task 01 source ingest contract
- Task 02 character/persona setup contract
- Batch 08 closeout and provider failure/idempotency/audit inspection tests

## Goal

Reconcile the source ingest and character/persona setup contracts into shared provider-backed write
conventions before an implementation batch is written.

## Output

Create:

- `plans/batch_09_provider_backed_api_planning/03_provider_backed_write_contract_matrix.md`

## Requirements

The matrix must specify:

- common write response envelope fields and route naming conventions;
- common status codes and error codes;
- audit event operation naming and related-ID conventions;
- workflow type naming, workflow link relation names, and persisted-ID shape;
- idempotency key location, body/header matching rules, replay payload expectations, and conflict
  behavior;
- redaction defaults and fields that must never be exposed;
- provider failure, provider validation failure, partial persistence, retryable conflict, guard
  failure, and critic/follow-up failure shapes;
- read-only inspection/debugging expectations through existing audit/workflow routes;
- implementation gating checklist for any provider-backed route;
- which candidate should be implemented first and why.

## Non-Goals

- Do not implement routes or source code changes.
- Do not introduce a new generic platform API style beyond the current local-first MVP needs.
- Do not broaden scope to turn execution, summary, benchmark, auth/workspace, UI, deployment, or
  unrelated pagination changes.

## Verification

Run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this planning artifact on `planning/api-provider-write-contract-matrix`, push the branch
to `origin`, and do not merge back to `dev`.

Final report should include the reconciled conventions, implementation gating checklist, chosen
first workflow recommendation, and unresolved blockers.
