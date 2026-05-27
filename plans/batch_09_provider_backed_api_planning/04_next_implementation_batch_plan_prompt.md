# Task 04 Prompt: Next Implementation Batch Plan

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_09_provider_backed_api_planning/BATCH_09_PROVIDER_BACKED_API_PLANNING.md`.

## Branch

Start from the completed Task 03 branch:

```powershell
git switch planning/api-provider-write-contract-matrix
git status --short --branch
git switch -c planning/batch-10-provider-api-implementation
```

## Scheduling

This task starts after Task 03 is complete.

## Read First

- Batch 09 overview plan
- Task 01 source ingest contract
- Task 02 character/persona setup contract
- Task 03 shared provider-backed write contract matrix
- `VIBE_CODING_GUIDE.md`
- Batch 08 closeout

## Goal

Create the next implementation batch plan and task prompts for the first accepted provider-backed
API workflow. The output should be ready for multi-agent execution in a later session.

## Output

Create a new implementation batch directory. Suggested name:

- `plans/batch_10_provider_backed_source_character_api/`

Expected files:

- `BATCH_10_PROVIDER_BACKED_SOURCE_CHARACTER_API.md`
- task prompt files for the selected implementation sequence

If Task 03 recommends implementing only source ingest first, scope Batch 10 accordingly and explain
why character/persona setup is deferred. If Task 03 recommends source ingest plus character/persona
setup in one implementation batch, define the dependencies and integration order explicitly.

## Requirements

The implementation batch plan must include:

- branch names and branch bases;
- dependency order and integration branches;
- exact expected route scope;
- expected application-service gaps;
- storage/migration expectations, if any;
- audit/workflow/idempotency/failure/redaction requirements;
- focused tests per task;
- closeout verification plan;
- non-goals and deferred routes.

## Non-Goals

- Do not implement routes or source changes in this planning task.
- Do not choose turn execution, summary, benchmark, auth/workspace/platform, UI, deployment, queues,
  or cursor migration unless earlier Batch 09 artifacts explicitly reject both source ingest and
  character/persona setup.

## Verification

Run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only planning artifacts on `planning/batch-10-provider-api-implementation`, push the branch
to `origin`, and do not merge back to `dev`.

Final report should include the selected implementation batch scope, task order, branches, tests,
and any blockers.
