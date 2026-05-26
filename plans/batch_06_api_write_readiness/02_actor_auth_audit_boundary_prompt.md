# Task 02 Prompt: Actor Auth Audit Boundary

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_06_api_write_readiness/BATCH_06_API_WRITE_READINESS.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c planning/api-actor-auth-audit
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task can start immediately.

It can run in parallel with:

- Task 01 Write Workflow Boundary Design
- Task 04 Pagination Filter Contract

Avoid editing their output files except for narrow references.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `README.md`
- `plans/batch_06_api_write_readiness/BATCH_06_API_WRITE_READINESS.md`
- `plans/batch_03_p2_planning/04_user_workspace_audit_model.md`
- `plans/batch_04_service_foundation/10_audit_readiness.md`
- `src/personality_jelly/application/audit.py` if present
- `src/personality_jelly/application/`
- `src/personality_jelly/storage/models.py`
- `src/personality_jelly/storage/repositories.py`

## Goal

Define the actor, auth, and audit boundary for future API write workflows without building a
platform auth system. The output should let later API tasks distinguish local explicit actor data
from deferred production authentication.

## Planning Requirements

- Define the minimum local actor model future write APIs should require, such as explicit
  `user_id`, optional actor label, or local operator context.
- State what is not part of the current phase: login, sessions, accounts, API keys, workspace
  membership, roles, billing, rate limits, and tenant isolation.
- Map future write workflows to audit expectations:
  - whether an audit event is required;
  - which actor, entity, action, reason, and result fields are needed;
  - whether payload-only audit readiness is enough or schema persistence is needed first.
- Define how manual memory review/edit/archive should record reasons and actor context.
- Define how provider-invoking workflows should record provider failure or retry outcomes without
  leaking secrets.
- Identify schema, repository, or application-service prerequisites before audit persistence can be
  implemented.
- Keep the boundary compatible with later platform auth, but do not design the full platform.

## Expected Write Scope

Likely files:

- `plans/batch_06_api_write_readiness/02_actor_auth_audit_boundary.md`

Avoid editing source code, tests, README, or `VIBE_CODING_GUIDE.md` unless a small status correction
is necessary.

## Non-Goals

- Do not add auth middleware, login flows, account tables, API key checks, or workspace features.
- Do not add audit migrations or write audit repositories.
- Do not add write API endpoints.
- Do not expose local filesystem paths, secrets, provider config, or raw stack traces.

## Verification

No automated tests are required for this planning task unless you make code changes.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `planning/api-actor-auth-audit`.

Development is complete only after the development branch is pushed. Do not merge this branch back
into `dev`. Push only the task branch to `origin` and report the branch name and commit hash. A
coordinator or maintainer will handle review and integration into `dev`.

In your final report, include:

- local actor/auth boundary;
- audit expectations by workflow;
- deferred platform concerns;
- schema or service prerequisites;
- checks run.
