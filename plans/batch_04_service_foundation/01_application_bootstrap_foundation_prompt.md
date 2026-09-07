# Task 01 Prompt: Application Bootstrap Foundation

Follow `VIBE_CODING_GUIDE.md` and `plans/batch_03_p2_planning/P2_ACCEPTANCE_CRITERIA.md`.

## Goal

Create the initial `personality_jelly.application` package and move reusable bootstrap concepts out
of CLI-only code without changing CLI behavior.

## Scope

- Add application package skeleton.
- Add database/session resource helpers if they can be extracted cleanly.
- Add provider/model role bundle types that mirror current roleplay, critic, memory curator, mode
  classifier, and retriever roles.
- Add minimal error normalization helpers only if useful.
- Keep CLI output and defaults unchanged.

## Non-Goals

- Do not add FastAPI.
- Do not change storage schemas.
- Do not change semantic runtime behavior.
- Do not move large CLI command bodies in this task.

## Verification

Run focused tests for CLI bootstrap/config/demo behavior and then `git status --short --branch`.
