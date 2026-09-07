# Task 01 Prompt: Write Workflow Boundary Design

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_06_api_write_readiness/BATCH_06_API_WRITE_READINESS.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c planning/api-write-workflows
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task can start immediately.

It can run in parallel with:

- Task 02 Actor Auth Audit Boundary
- Task 04 Pagination Filter Contract

Avoid editing their output files except for narrow references.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `README.md`
- `plans/batch_06_api_write_readiness/BATCH_06_API_WRITE_READINESS.md`
- `plans/batch_05_read_only_api/BATCH_05_READ_ONLY_API.md`
- `src/personality_jelly/api/app.py`
- `src/personality_jelly/api/dependencies.py`
- `src/personality_jelly/api/errors.py`
- `src/personality_jelly/application/`
- `src/personality_jelly/runtime/`
- `src/personality_jelly/storage/repositories.py`

## Goal

Design the future API write workflow boundary without implementing write routes. The output should
make it clear which write workflows are safe candidates for a later batch, which application
service contracts they require, and how transactions and partial persistence should behave.

## Planning Requirements

- Classify deferred write workflows into:
  - safe first implementation candidates;
  - candidates requiring more application-service work;
  - candidates that should stay CLI-only or deferred.
- Cover at least:
  - source ingest;
  - character creation and persona setup;
  - conversation creation;
  - turn execution;
  - summary generation;
  - benchmark execution;
  - memory review/edit/archive;
  - audit persistence.
- Define request and response contract expectations at a high level, including required explicit
  IDs and idempotency considerations.
- Define transaction boundaries and partial-persistence behavior for each candidate workflow.
- Define error families for validation, missing IDs, provider failures, guard/critic failures,
  partial writes, and unexpected errors.
- Identify any service functions that must be created or hardened before API implementation starts.
- Keep `personality_jelly.api` as an adapter; workflow behavior belongs in `application` or domain
  services.

## Expected Write Scope

Likely files:

- `plans/batch_06_api_write_readiness/01_write_workflow_boundary_design.md`

Avoid editing source code, tests, README, or `VIBE_CODING_GUIDE.md` unless a small status correction
is necessary.

## Non-Goals

- Do not add HTTP write routes.
- Do not add auth, workspace, API keys, CORS, deployment, or UI.
- Do not change repository schemas or migrations.
- Do not change semantic prompts, benchmark pass/fail logic, retrieval behavior, or memory guard
  rules.

## Verification

No automated tests are required for this planning task unless you make code changes.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `planning/api-write-workflows`.

Development is complete only after the development branch is pushed. Do not merge this branch back
into `dev`. Push only the task branch to `origin` and report the branch name and commit hash. A
coordinator or maintainer will handle review and integration into `dev`.

In your final report, include:

- recommended first write workflow candidates;
- transaction and partial-persistence policy;
- application-service prerequisites;
- explicit non-goals;
- checks run.
