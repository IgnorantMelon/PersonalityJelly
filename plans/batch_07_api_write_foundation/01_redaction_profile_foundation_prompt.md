# Task 01 Prompt: Redaction Profile Foundation

Follow `VIBE_CODING_GUIDE.md`,
`plans/batch_07_api_write_foundation/BATCH_07_API_WRITE_FOUNDATION.md`, and
`plans/batch_06_api_write_readiness/03_api_redaction_policy.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/api-redaction-foundation
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task can start immediately and can run in parallel with Task 02.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `plans/batch_07_api_write_foundation/BATCH_07_API_WRITE_FOUNDATION.md`
- `plans/batch_06_api_write_readiness/03_api_redaction_policy.md`
- `src/personality_jelly/api/schemas.py`
- `src/personality_jelly/api/routes/`
- `src/personality_jelly/application/`
- `src/personality_jelly/runtime/context.py`
- `src/personality_jelly/llm/tracing.py`
- `src/personality_jelly/storage/models.py`
- `tests/test_api_*.py`

## Goal

Implement the shared redaction foundation needed by new write-era API responses without changing
existing Batch 05 read-only response behavior.

## Implementation Requirements

- Add a transport-neutral redaction profile model, with at least:
  - `local_default`;
  - `local_debug`;
  - `platform_default`.
- Add shared helper functions or serializers that can recursively sanitize dictionaries, lists, and
  Pydantic models used by API/application response models.
- Ensure default redaction removes or replaces:
  - secrets, API keys, auth headers, tokens;
  - provider config and raw provider request/response payloads;
  - local filesystem paths;
  - raw prompts and prompt-like payloads;
  - raw user text unless the response model explicitly allows a safe preview;
  - full memory content/reason fields unless explicitly debug-scoped;
  - full source text/chunk text unless explicitly debug-scoped;
  - stack traces and internal exception details.
- Keep raw persisted values available in domain/storage/application inspection layers.
- Do not migrate existing Batch 05 route responses in this task unless needed for a focused helper
  test; compatibility stays intact.
- Add focused unit tests for recursive redaction behavior and representative safe/default outputs.

## Expected Write Scope

Likely files:

- `src/personality_jelly/api/redaction.py` or an equivalent shared API/application serializer module;
- `src/personality_jelly/api/schemas.py` if profile enums or response models belong there;
- focused tests under `tests/`;
- minimal package exports if needed.

Avoid route behavior changes outside the helper integration points required by tests.

## Non-Goals

- Do not add auth, permissions, roles, API keys, write routes, or platform workspace logic.
- Do not remove raw fields from storage or domain models.
- Do not retrofit every Batch 05 read-only route to redacted defaults.
- Do not add provider-backed workflow behavior.

## Verification

Run focused tests for the new redaction helpers. Run broader API tests if existing route behavior is
touched.

Before completion, run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this task's changes on `feature/api-redaction-foundation`, push the branch to `origin`,
and do not merge back to `dev`.

Final report should include:

- redaction profile API;
- sensitive fields covered;
- tests run;
- compatibility caveats.
