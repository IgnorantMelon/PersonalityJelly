# Task 02 Prompt: Multi-Work / Multi-Character Boundary Audit

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent
baseline in `VIBE_CODING_GUIDE.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c planning/multi-entity-boundary-audit
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task is Wave A and can start immediately.

It can run in parallel with:

- Task 01 FastAPI Service Boundary Design
- Task 03 Runtime Workflow Observability Plan

Task 04 User / Workspace / Audit Concept Design should use this task's draft or final report.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `plans/batch_03_p2_planning/P2_PLANNING_ORCHESTRATION.md`
- `src/personality_jelly/domain/models.py`
- `src/personality_jelly/storage/orm.py`
- `src/personality_jelly/storage/repositories.py`
- `src/personality_jelly/storage/migrations.py`
- `src/personality_jelly/runtime/context.py`
- `src/personality_jelly/runtime/turn.py`
- `src/personality_jelly/evaluation/benchmark.py`
- `src/personality_jelly/evaluation/retrieval_benchmark.py`
- relevant CLI commands in `src/personality_jelly/cli/main.py`

## Goal

Audit the current codebase for assumptions that may block future multi-work, multi-character,
multi-user, or workspace-oriented behavior.

This is an audit task. Do not change schemas, migrations, repository contracts, or behavior.

## Audit Requirements

- Track whether these IDs are preserved through important flows:
  - `source_work_id`
  - `character_id`
  - `user_id`
  - `conversation_id`
  - `persona_version_id`
  - `memory_scope`
  - `interaction_mode`
  - source `chunk_id` / evidence refs
- Identify explicit or implicit single-work assumptions.
- Identify explicit or implicit single-character assumptions.
- Identify places where user-specific memory or relationship memory could be confused with canon.
- Identify storage and repository areas that are already ready for P2 expansion.
- Identify CLI workflows that currently hide important IDs from users or downstream automation.
- Include file-level references for each risk or readiness item.
- Do not rely on broad claims; ground conclusions in code paths or tests.

## Expected Write Scope

Likely files:

- `plans/batch_03_p2_planning/02_multi_entity_boundary_audit.md`

Avoid editing source code, tests, README, or `VIBE_CODING_GUIDE.md` unless a small status correction
is necessary.

## Verification

No automated tests are required for this planning task unless you make code changes.

Before completion, run:

```powershell
git status --short --branch
```

## Completion

Commit only this task's changes on `planning/multi-entity-boundary-audit`.

Do not merge this branch back into `dev`. Push only the task branch to `origin` and report the
branch name and commit hash. A coordinator or maintainer will handle review and integration into
`dev`.

In your final report, include:

- major single-work assumptions;
- major single-character assumptions;
- ID propagation risks;
- areas already ready for P2;
- recommended follow-up tasks.
