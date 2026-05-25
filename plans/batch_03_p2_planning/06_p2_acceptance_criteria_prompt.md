# Task 06 Prompt: P2 Acceptance Criteria Snapshot

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent
baseline in `VIBE_CODING_GUIDE.md`.

## Branch

This task should start only after Tasks 01-05 are accepted and integrated into `dev`.

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c planning/p2-acceptance-criteria
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task is Wave D and must wait for:

- Task 01 FastAPI Service Boundary Design
- Task 02 Multi-Work / Multi-Character Boundary Audit
- Task 03 Runtime Workflow Observability Plan
- Task 04 User / Workspace / Audit Concept Design
- Task 05 CLI/API Shared Service Refactor Plan

Do not start while earlier planning branches are still unaccepted or unintegrated.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `README.md`
- `plans/batch_03_p2_planning/P2_PLANNING_ORCHESTRATION.md`
- final reports and integrated planning docs for Tasks 01-05
- current `plans/` structure

## Goal

Consolidate Batch 03 outputs into a clear P2 acceptance snapshot and define the recommended first
implementation batch after planning.

This is a planning closeout task. Do not introduce product behavior.

## Planning Requirements

- Summarize the accepted P2 service boundary.
- Summarize the accepted data-boundary risks and prerequisites.
- Summarize the user/workspace/audit decisions.
- Summarize the runtime observability requirements.
- Summarize the CLI/API shared service refactor plan.
- Define P2 acceptance criteria in concrete terms.
- Define non-goals that remain out of scope for P2 implementation.
- Propose Batch 04 implementation tasks, including order and parallelism.
- Update `VIBE_CODING_GUIDE.md` only if current engineering priorities or status become stale.
- Update `README.md` only if public status becomes stale.

## Expected Write Scope

Likely files:

- `plans/batch_03_p2_planning/P2_ACCEPTANCE_CRITERIA.md`
- possibly `plans/batch_04_service_foundation/` prompt drafts if the accepted plan calls for them
- possibly `VIBE_CODING_GUIDE.md`
- possibly `README.md`

Avoid source-code changes.

## Verification

No automated tests are required unless you make code changes.

If you update only docs, run:

```powershell
git status --short --branch
```

If you make any code or test changes, run focused tests and then the full suite:

```powershell
.\.venv\Scripts\python -m pytest
```

## Completion

Commit only this task's changes on `planning/p2-acceptance-criteria`.

Do not merge this branch back into `dev`. Push only the task branch to `origin` and report the
branch name and commit hash. A coordinator or maintainer will handle review and integration into
`dev`.

In your final report, include:

- accepted P2 criteria;
- docs updated;
- Batch 04 recommendation;
- tests or checks run;
- unresolved decisions that need human review.
