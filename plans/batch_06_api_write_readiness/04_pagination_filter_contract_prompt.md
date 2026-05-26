# Task 04 Prompt: Pagination Filter Contract

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_06_api_write_readiness/BATCH_06_API_WRITE_READINESS.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c planning/api-pagination-filters
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task can start immediately.

It can run in parallel with:

- Task 01 Write Workflow Boundary Design
- Task 02 Actor Auth Audit Boundary

Avoid editing their output files except for narrow references.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `README.md`
- `plans/batch_06_api_write_readiness/BATCH_06_API_WRITE_READINESS.md`
- `plans/batch_05_read_only_api/BATCH_05_READ_ONLY_API.md`
- `src/personality_jelly/api/routes/`
- `src/personality_jelly/api/schemas.py`
- `src/personality_jelly/application/`
- `src/personality_jelly/storage/repositories.py`
- `tests/test_api_*.py`

## Goal

Define shared API list, pagination, ordering, and filter conventions for future read and write-era
endpoints. The output should prevent each route family from inventing incompatible query behavior.

## Planning Requirements

- Inventory current Batch 05 list endpoints and their query params.
- Define default and maximum `limit` values.
- Decide whether the next implementation should keep simple limit-only lists, add offset, or
  prepare cursor-based pagination.
- Define stable ordering expectations for every list family.
- Define naming conventions for filters such as `character_id`, `source_work_id`, `conversation_id`,
  `user_id`, `status`, `scope`, `operation`, `schema_name`, `provider_name`, `model_name`,
  `test_suite`, `failed_only`, and `include_chunks`.
- Define response envelope expectations for lists, including item arrays, count/has_more/cursor
  fields if applicable, and error behavior for invalid filters.
- Identify repository or application-service ordering/filter gaps.
- Include compatibility guidance for existing Batch 05 endpoints.

## Expected Write Scope

Likely files:

- `plans/batch_06_api_write_readiness/04_pagination_filter_contract.md`

Avoid editing source code, tests, README, or `VIBE_CODING_GUIDE.md` unless a small status correction
is necessary.

## Non-Goals

- Do not change current API route behavior.
- Do not implement pagination, cursors, repository changes, or response envelope changes.
- Do not add write routes, auth, CORS, deployment, or UI.

## Verification

No automated tests are required for this planning task unless you make code changes.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `planning/api-pagination-filters`.

Development is complete only after the development branch is pushed. Do not merge this branch back
into `dev`. Push only the task branch to `origin` and report the branch name and commit hash. A
coordinator or maintainer will handle review and integration into `dev`.

In your final report, include:

- current list endpoint inventory;
- recommended limit/pagination approach;
- filter and ordering conventions;
- compatibility notes;
- checks run.
