# Task 07 Prompt: Batch 05 Closeout Verification

Follow `VIBE_CODING_GUIDE.md` and `plans/batch_05_read_only_api/BATCH_05_READ_ONLY_API.md`.

## Goal

Complete Batch 05 with a clean verification pass and an updated project status snapshot.

## Scope

- Run focused API tests.
- Run focused CLI inspection tests to confirm the CLI still uses the service layer correctly.
- Run the full pytest suite.
- Confirm `git status --short --branch` is clean after commit.
- Update the Batch 05 plan or `VIBE_CODING_GUIDE.md` status if implementation reality differs
  from the initial plan.
- Record any deferred work that should start Batch 06.

## Non-Goals

- Do not add new behavior during closeout except small documentation/status corrections.
- Do not fix unrelated tests or refactor unrelated modules.
- Do not merge write API work into this verification task.

## Acceptance Checklist

- `personality_jelly.api.create_app` exists and app-factory tests pass.
- `GET /health` passes against a migrated test database.
- Read-only endpoint tests cover conversations, context packages, characters, claims, memories,
  source chunks, critic reports, failure cases, LLM traces, OOC eval runs, and retrieval eval runs.
- Structured error envelope tests pass.
- No API endpoint writes source, character, conversation, message, summary, memory, benchmark, or
  audit state.
- Existing CLI list/show behavior remains covered by tests.
- Full pytest suite passes.

## Verification

Run `.\.venv\Scripts\python -m pytest` before final report.
