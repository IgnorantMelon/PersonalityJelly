# Task 05 Prompt: Trace Workflow Correlation

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_06_api_write_readiness/BATCH_06_API_WRITE_READINESS.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c planning/api-trace-correlation
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task should preferably start after Task 01 has enough context because write workflow shape
affects correlation needs.

Avoid editing other Batch 06 task outputs except for narrow references.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `README.md`
- `plans/batch_06_api_write_readiness/BATCH_06_API_WRITE_READINESS.md`
- `plans/batch_03_p2_planning/03_runtime_observability_plan.md`
- `plans/batch_05_read_only_api/BATCH_05_READ_ONLY_API.md`
- `src/personality_jelly/llm/tracing.py`
- `src/personality_jelly/runtime/turn.py`
- `src/personality_jelly/runtime/context.py`
- `src/personality_jelly/application/`
- `src/personality_jelly/storage/models.py`
- `src/personality_jelly/storage/migrations/`

## Goal

Plan request and workflow correlation for future API write routes so a maintainer can connect an
HTTP request, application workflow, persisted records, LLM traces, critic reports, memories,
failure cases, and benchmark outputs.

## Planning Requirements

- Define correlation concepts:
  - request ID;
  - workflow/run ID;
  - LLM trace ID;
  - conversation/message/context package IDs;
  - eval run IDs;
  - failure case IDs;
  - optional audit event IDs.
- Decide what should be generated per HTTP request versus per application workflow.
- Define how correlation IDs should flow through application services without coupling domain code
  to FastAPI.
- Identify where existing LLM trace records already carry enough linkage and where schema changes
  may be needed.
- Propose migration options if new correlation columns or workflow-run tables are needed.
- Define API response and error-envelope expectations for returning correlation IDs.
- Define test expectations for future implementation.

## Expected Write Scope

Likely files:

- `plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`

Avoid editing source code, tests, README, or `VIBE_CODING_GUIDE.md` unless a small status correction
is necessary.

## Non-Goals

- Do not add migrations, models, trace columns, workflow-run tables, or request middleware.
- Do not change existing trace persistence.
- Do not add write routes, auth, CORS, deployment, or UI.
- Do not add external observability frameworks.

## Verification

No automated tests are required for this planning task unless you make code changes.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `planning/api-trace-correlation`.

Development is complete only after the development branch is pushed. Do not merge this branch back
into `dev`. Push only the task branch to `origin` and report the branch name and commit hash. A
coordinator or maintainer will handle review and integration into `dev`.

In your final report, include:

- correlation model recommendation;
- required schema or service changes;
- error-envelope and response expectations;
- future tests to add;
- checks run.
