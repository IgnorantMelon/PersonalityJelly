# Task 06 Prompt: Batch 07 Closeout Verification

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_07_api_write_foundation/BATCH_07_API_WRITE_FOUNDATION.md`.

## Branch

Start from the latest `dev` after Tasks 01-05 have been merged by a coordinator and create:

```powershell
git switch dev
git status --short --branch
git switch -c chore/batch-07-write-foundation-closeout
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task starts only after Tasks 01-05 are complete and merged into `dev`.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `plans/batch_07_api_write_foundation/BATCH_07_API_WRITE_FOUNDATION.md`
- all completed Batch 07 task outputs or merged implementation commits;
- `plans/batch_06_api_write_readiness/06_batch_06_acceptance_next_recommendation.md`
- relevant API/application tests.

## Goal

Verify Batch 07 closeout, confirm the implemented write foundation remains inside the accepted
scope, and update project status docs.

## Verification Requirements

- Confirm the implemented route set includes only the accepted deterministic write routes.
- Confirm no provider-backed write workflow is exposed through HTTP.
- Confirm write route handlers are thin adapters over `personality_jelly.application`.
- Confirm redaction defaults apply to write-era responses.
- Confirm request/workflow correlation IDs appear in write success responses and sanitized errors.
- Confirm local actor context and reason requirements are enforced for manual memory mutations.
- Confirm payload-only audit metadata is returned where required and no persistent audit storage was
  added unless a maintainer explicitly changed scope.
- Run focused API/application tests for Batch 07 routes and foundations.
- Run full pytest if shared behavior was touched.

## Expected Write Scope

Likely files:

- `plans/batch_07_api_write_foundation/BATCH_07_API_WRITE_FOUNDATION.md` closeout note;
- `README.md` status update;
- `VIBE_CODING_GUIDE.md` status update;
- optional closeout report under this directory if useful.

Avoid source changes except small test or docs corrections needed to close the batch.

## Non-Goals

- Do not add new write workflows during closeout.
- Do not add provider-backed routes, auth/workspace/platform features, deployment, CORS, UI, or
  persistent audit.
- Do not widen route scope to source ingest, character/persona setup, turn execution, summary, or
  benchmarks.

## Completion

Commit only closeout changes on `chore/batch-07-write-foundation-closeout`, push the branch to
`origin`, and do not merge back to `dev`.

Final report should include:

- Batch 07 acceptance summary;
- route set verified;
- tests run;
- docs updated;
- next recommended batch or blockers.
