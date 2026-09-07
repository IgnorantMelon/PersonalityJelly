# Task 04 Prompt: User / Workspace / Audit Concept Design

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent
baseline in `VIBE_CODING_GUIDE.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c planning/user-workspace-audit-model
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task is Wave B.

Prefer waiting for at least a draft of:

- Task 02 Multi-Work / Multi-Character Boundary Audit

It may run while Task 01 or Task 03 is still active, but avoid making final service/API assumptions
that conflict with those tasks.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `plans/batch_03_p2_planning/P2_PLANNING_ORCHESTRATION.md`
- Task 02 draft or final report
- `src/personality_jelly/domain/models.py`
- `src/personality_jelly/storage/orm.py`
- `src/personality_jelly/storage/repositories.py`
- `src/personality_jelly/runtime/conversation.py`
- `src/personality_jelly/runtime/turn.py`
- `src/personality_jelly/memory/curator.py`
- `src/personality_jelly/memory/guard.py`

## Goal

Design the minimum user, workspace, and audit concepts needed for P2 planning without building a
permission system or platform layer.

This is a concept-design task. Do not add models, migrations, or auth dependencies.

## Planning Requirements

- Define the minimum concept of `user` for local MVP continuity.
- Define whether `workspace` is needed in early P2 or should remain a later platform concept.
- Define audit log needs for:
  - manual memory review/edit/archive;
  - canon claim review or correction;
  - provider/model calls that affect semantic state;
  - benchmark or failure-case review;
  - future API write operations.
- Clarify ownership boundaries for:
  - source works;
  - characters;
  - persona versions;
  - conversations;
  - user memory;
  - relationship memory;
  - context packages;
  - critic reports;
  - LLM traces;
  - evaluation runs.
- Identify which ownership rules are required for P2 and which can wait.
- Keep canon and memory boundaries strict.

## Expected Write Scope

Likely files:

- `plans/batch_03_p2_planning/04_user_workspace_audit_model.md`

Avoid editing source code, tests, README, or `VIBE_CODING_GUIDE.md` unless a small status correction
is necessary.

## Verification

No automated tests are required for this planning task unless you make code changes.

Before completion, run:

```powershell
git status --short --branch
```

## Completion

Commit only this task's changes on `planning/user-workspace-audit-model`.

Do not merge this branch back into `dev`. Push only the task branch to `origin` and report the
branch name and commit hash. A coordinator or maintainer will handle review and integration into
`dev`.

In your final report, include:

- user concept recommendation;
- workspace timing recommendation;
- audit log minimum requirements;
- ownership rules;
- items deferred beyond P2.
