# Task 05 Prompt: Batch 09 Closeout

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_09_provider_backed_api_planning/BATCH_09_PROVIDER_BACKED_API_PLANNING.md`.

## Branch

Start from clean `dev` after Tasks 01-04 have been merged by the coordinator and create:

```powershell
git switch dev
git status --short --branch
git switch -c planning/batch-09-closeout
```

If the branch already exists, inspect it and continue only if it is clearly the intended closeout
branch.

## Scheduling

This task starts only after Tasks 01-04 are complete and merged into `dev` in dependency order.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- Batch 09 overview plan
- all completed Batch 09 planning artifacts
- Batch 08 closeout

## Goal

Verify Batch 09 planning acceptance, update current project guidance, and leave a clean handoff for
the next implementation batch.

## Output

Create:

- `plans/batch_09_provider_backed_api_planning/BATCH_09_CLOSEOUT.md`

Update as appropriate:

- `VIBE_CODING_GUIDE.md`
- `README.md` only if the public-facing status needs a concise planning update
- Batch 09 overview plan closeout status

## Verification Requirements

- Confirm Batch 09 did not add provider-backed routes or source behavior changes.
- Confirm source ingest and character/persona setup contracts are explicit enough for implementation.
- Confirm the shared contract matrix reconciles route, redaction, audit/workflow, idempotency,
  persisted-ID, and failure/partial-persistence conventions.
- Confirm the next implementation batch plan exists and has executable task prompts.
- Confirm docs agree on the selected next implementation scope.

## Non-Goals

- Do not implement source ingest, character/persona setup, turn execution, summary, benchmark, or
  any provider-backed write route.
- Do not add auth/workspace/platform, UI, deployment, queues, CORS, external observability, or
  unrelated dependency changes.

## Verification

Run:

```powershell
git diff --check
git status --short --branch
```

No pytest run is required for docs-only closeout unless source or test files changed.

## Completion

Commit only closeout docs on `planning/batch-09-closeout`, push the branch to `origin`, and do not
merge back to `dev`.

Final report should include the selected next implementation scope, planning artifacts merged,
docs updated, validation run, and unresolved blockers.
