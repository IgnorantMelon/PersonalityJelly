# Task 01 Prompt: FastAPI Service Boundary Design

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent
baseline in `VIBE_CODING_GUIDE.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c planning/fastapi-service-boundary
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task is Wave A and can start immediately.

It can run in parallel with:

- Task 02 Multi-Work / Multi-Character Boundary Audit
- Task 03 Runtime Workflow Observability Plan

Avoid editing files owned by those tasks except for narrow references.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `README.md`
- `plans/batch_03_p2_planning/P2_PLANNING_ORCHESTRATION.md`
- `src/personality_jelly/cli/main.py`
- `src/personality_jelly/runtime/turn.py`
- `src/personality_jelly/runtime/context.py`
- `src/personality_jelly/evaluation/benchmark.py`
- `src/personality_jelly/evaluation/retrieval_benchmark.py`
- `src/personality_jelly/storage/repositories.py`

## Goal

Design the first P2 service/API boundary for the current CLI-first MVP. The output should make it
clear which existing workflows can become service operations, which should stay CLI-only, and which
API surfaces should be read-only before write workflows are introduced.

This is a design task. Do not add FastAPI or implementation dependencies.

## Planning Requirements

- Propose a service boundary that reuses existing modules instead of moving business logic into API
  handlers.
- Separate read-only inspection endpoints from write/workflow endpoints.
- Define candidate request and response model families at a high level.
- Define error-model expectations for missing IDs, validation failures, provider failures, and
  guard/critic failures.
- Identify which CLI workflows map naturally to API/service operations:
  - character inspection;
  - conversation inspection;
  - context package inspection;
  - critic report inspection;
  - LLM trace inspection;
  - benchmark run inspection;
  - ingest source;
  - create character;
  - start conversation;
  - run turn;
  - run benchmark.
- Explicitly list non-goals for the first service phase.
- Call out any code areas that must be refactored before API implementation should start.

## Expected Write Scope

Likely files:

- `plans/batch_03_p2_planning/01_fastapi_service_boundary_design.md`

Avoid editing source code, tests, README, or `VIBE_CODING_GUIDE.md` unless a small status correction
is necessary.

## Verification

No automated tests are required for this planning task unless you make code changes.

Before completion, run:

```powershell
git status --short --branch
```

## Completion

Commit only this task's changes on `planning/fastapi-service-boundary`.

Do not merge this branch back into `dev`. Push only the task branch to `origin` and report the
branch name and commit hash. A coordinator or maintainer will handle review and integration into
`dev`.

In your final report, include:

- service/API boundary summary;
- read-only versus write workflow split;
- explicit non-goals;
- refactor prerequisites found;
- tests or checks run.
