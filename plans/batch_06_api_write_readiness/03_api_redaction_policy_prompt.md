# Task 03 Prompt: API Redaction Policy

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_06_api_write_readiness/BATCH_06_API_WRITE_READINESS.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c planning/api-redaction-policy
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task should preferably start after Tasks 01 and 02 have enough context, but it can begin
earlier if it stays focused on current read-only fields.

Avoid editing other Batch 06 task outputs except for narrow references.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `README.md`
- `plans/batch_06_api_write_readiness/BATCH_06_API_WRITE_READINESS.md`
- `plans/batch_05_read_only_api/BATCH_05_READ_ONLY_API.md`
- `src/personality_jelly/api/routes/`
- `src/personality_jelly/application/inspection.py` or related inspection modules
- `src/personality_jelly/runtime/context.py`
- `src/personality_jelly/llm/tracing.py`
- `src/personality_jelly/storage/models.py`

## Goal

Define an API redaction and exposure policy before future clients depend on sensitive inspection
fields. The output should state what the local read-only API may expose today, what should become
redacted by default, and which fields require explicit debug or privileged access in later phases.

## Planning Requirements

- Inventory sensitive API-visible data families:
  - assembled prompts and context package content;
  - raw user and assistant messages;
  - user memories and relationship memories;
  - source chunks and evidence snippets;
  - raw LLM output, parsed output, validation errors, provider/model names, and trace metadata;
  - critic reports and failure cases;
  - benchmark cases and run outputs.
- Define field-level default exposure for local MVP, future local debug clients, and future
  platform clients.
- Define redaction behavior for secrets, provider config, local filesystem paths, raw prompts,
  raw user text, and stack traces.
- Decide whether redaction belongs in application inspection services, API response models, or a
  shared serializer layer.
- Define test expectations for later implementation, including fields that must never appear in
  default responses.
- Preserve the ability to debug local workflows without making broad exposure the default policy.

## Expected Write Scope

Likely files:

- `plans/batch_06_api_write_readiness/03_api_redaction_policy.md`

Avoid editing source code, tests, README, or `VIBE_CODING_GUIDE.md` unless a small status correction
is necessary.

## Non-Goals

- Do not implement redaction code.
- Do not remove current Batch 05 route fields.
- Do not add auth, roles, permission checks, or write routes.
- Do not redefine canon, memory, or semantic safety rules.

## Verification

No automated tests are required for this planning task unless you make code changes.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `planning/api-redaction-policy`.

Development is complete only after the development branch is pushed. Do not merge this branch back
into `dev`. Push only the task branch to `origin` and report the branch name and commit hash. A
coordinator or maintainer will handle review and integration into `dev`.

In your final report, include:

- sensitive field inventory;
- default redaction policy;
- implementation placement recommendation;
- future tests to add;
- checks run.
