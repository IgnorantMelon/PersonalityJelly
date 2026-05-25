# Task 05 Prompt: CLI/API Shared Service Refactor Plan

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent
baseline in `VIBE_CODING_GUIDE.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c planning/shared-service-refactor
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task is Wave C.

Must wait for:

- Task 01 FastAPI Service Boundary Design
- Task 03 Runtime Workflow Observability Plan

Prefer also reading the latest Task 02 and Task 04 outputs before finalizing.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `plans/batch_03_p2_planning/P2_PLANNING_ORCHESTRATION.md`
- Task 01 final report
- Task 03 final report
- Task 02 and Task 04 outputs if available
- `src/personality_jelly/cli/main.py`
- `src/personality_jelly/ingestion/service.py`
- `src/personality_jelly/characters/service.py`
- `src/personality_jelly/extraction/service.py`
- `src/personality_jelly/persona/compiler.py`
- `src/personality_jelly/runtime/turn.py`
- `src/personality_jelly/runtime/context.py`
- `src/personality_jelly/evaluation/benchmark.py`
- `src/personality_jelly/evaluation/retrieval_benchmark.py`

## Goal

Plan how future CLI and API entry points can share reusable application services without duplicating
workflow orchestration or pushing business behavior into FastAPI handlers.

This is a refactor-planning task. Do not perform the refactor in this branch.

## Planning Requirements

- Identify major orchestration blocks currently living in `cli/main.py`.
- Classify each block as:
  - keep CLI-only;
  - move to existing service module;
  - move to a new application service module;
  - leave unchanged until a later phase.
- Propose a minimal service layer shape for:
  - ingestion/demo bootstrap;
  - character extraction and persona compilation;
  - conversation start and turn execution;
  - inspection/read-only diagnostics;
  - benchmark execution and reporting.
- Preserve current CLI output compatibility as a constraint.
- Identify tests that should protect the refactor when it happens.
- Recommend an implementation order for Batch 04.
- Avoid proposing broad rewrites of storage, runtime, or CLI.

## Expected Write Scope

Likely files:

- `plans/batch_03_p2_planning/05_shared_service_refactor_plan.md`

Avoid editing source code, tests, README, or `VIBE_CODING_GUIDE.md` unless a small status correction
is necessary.

## Verification

No automated tests are required for this planning task unless you make code changes.

Before completion, run:

```powershell
git status --short --branch
```

## Completion

Commit only this task's changes on `planning/shared-service-refactor`.

Do not merge this branch back into `dev`. Push only the task branch to `origin` and report the
branch name and commit hash. A coordinator or maintainer will handle review and integration into
`dev`.

In your final report, include:

- orchestration blocks found;
- proposed service layer shape;
- CLI compatibility constraints;
- recommended Batch 04 implementation order;
- tests or checks run.
