# Task 06 Prompt: Batch 06 Acceptance And Next Recommendation

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_06_api_write_readiness/BATCH_06_API_WRITE_READINESS.md`.

## Branch

Start from the latest `dev` after Tasks 01-05 have been merged by a coordinator and create:

```powershell
git switch dev
git status --short --branch
git switch -c planning/batch-06-closeout
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task starts after Tasks 01-05 are complete and merged into `dev`.

Do not start this closeout task from unmerged task branches unless a maintainer explicitly asks for
manual reconciliation.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `README.md`
- `plans/batch_06_api_write_readiness/BATCH_06_API_WRITE_READINESS.md`
- `plans/batch_06_api_write_readiness/01_write_workflow_boundary_design.md`
- `plans/batch_06_api_write_readiness/02_actor_auth_audit_boundary.md`
- `plans/batch_06_api_write_readiness/03_api_redaction_policy.md`
- `plans/batch_06_api_write_readiness/04_pagination_filter_contract.md`
- `plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`
- `plans/batch_05_read_only_api/BATCH_05_READ_ONLY_API.md`

## Goal

Close Batch 06 by reconciling the five planning outputs into one acceptance snapshot and one
recommended next implementation batch. The output should tell future agents exactly what to build
next, what remains deferred, and which risks must be resolved before write routes are exposed.

## Planning Requirements

- Confirm every Batch 06 goal has a corresponding planning output.
- Summarize the accepted contracts for:
  - write workflow candidates;
  - actor/auth/audit boundaries;
  - redaction defaults;
  - pagination/filter conventions;
  - trace/workflow correlation.
- Identify conflicts or gaps between Tasks 01-05 and resolve them in the closeout document or mark
  them as implementation blockers.
- Recommend the next batch name and scope, such as an API write-foundation batch or a redaction
  implementation batch.
- Define the first next-batch task order and prerequisites at a high level.
- Update `VIBE_CODING_GUIDE.md` and `README.md` only if Batch 06 closeout changes the current
  project status.

## Expected Write Scope

Likely files:

- `plans/batch_06_api_write_readiness/06_batch_06_acceptance_next_recommendation.md`
- `plans/batch_06_api_write_readiness/BATCH_06_API_WRITE_READINESS.md`
- `VIBE_CODING_GUIDE.md` if status needs updating
- `README.md` if public status needs a concise update

Avoid source code, tests, dependency files, and unrelated docs.

## Non-Goals

- Do not implement write endpoints.
- Do not add migrations, auth, redaction code, pagination code, tracing code, deployment, CORS, or
  UI.
- Do not rewrite earlier task outputs except for clear factual corrections.

## Verification

No automated tests are required for this planning task unless you make code changes.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `planning/batch-06-closeout`.

Development is complete only after the development branch is pushed. Do not merge this branch back
into `dev`. Push only the task branch to `origin` and report the branch name and commit hash. A
coordinator or maintainer will handle review and integration into `dev`.

In your final report, include:

- Batch 06 acceptance summary;
- recommended next batch and task order;
- unresolved blockers;
- docs updated;
- checks run.
