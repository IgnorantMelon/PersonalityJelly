# Task 03 Prompt: Local Actor Audit Boundary

Follow `VIBE_CODING_GUIDE.md`,
`plans/batch_07_api_write_foundation/BATCH_07_API_WRITE_FOUNDATION.md`, and
`plans/batch_06_api_write_readiness/02_actor_auth_audit_boundary.md`.

## Branch

Start from the latest `dev` after Tasks 01 and 02 have enough context and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/api-local-actor-audit
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task should start after Tasks 01 and 02 are merged or after their interfaces are stable enough
to reference. Avoid editing their files except for narrow integration fixes.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `plans/batch_07_api_write_foundation/BATCH_07_API_WRITE_FOUNDATION.md`
- `plans/batch_06_api_write_readiness/02_actor_auth_audit_boundary.md`
- `plans/batch_06_api_write_readiness/03_api_redaction_policy.md`
- `plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`
- `src/personality_jelly/application/audit.py`
- `src/personality_jelly/application/`
- `src/personality_jelly/storage/repositories.py`
- `tests/`

## Goal

Implement the local actor context and payload-only audit boundary that later deterministic write
services can reuse, without adding auth middleware or persistent audit storage.

## Implementation Requirements

- Add transport-neutral local actor context models suitable for application services.
- Require explicit actor data for future write services:
  - actor type;
  - actor ID;
  - optional actor label/metadata;
  - workflow reason when required by the operation.
- Keep actor context separate from production auth and user account semantics.
- Reuse or extend existing payload-only audit readiness models for manual memory operations.
- Define service-level validation helpers for required actor/reason fields.
- Ensure audit payloads can carry request/workflow correlation metadata from Task 02.
- Ensure payloads can be redacted or serialized through Task 01's redaction profile if available.
- Add focused tests for actor validation and payload-only audit construction.

## Expected Write Scope

Likely files:

- `src/personality_jelly/application/audit.py`;
- new or existing application models/helpers;
- focused tests.

Avoid HTTP route implementation unless needed for a narrow helper test.

## Non-Goals

- Do not add login, sessions, accounts, API keys, auth middleware, roles, or workspaces.
- Do not add audit database tables, repositories, migrations, or list/detail audit routes.
- Do not add conversation or memory write routes in this task.
- Do not expose secrets, local paths, or raw provider payloads in audit metadata.

## Verification

Run focused tests for local actor validation and audit payload construction.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `feature/api-local-actor-audit`, push the branch to `origin`,
and do not merge back to `dev`.

Final report should include:

- local actor model;
- audit payload behavior;
- tests run;
- deferred persistent audit/auth work.
