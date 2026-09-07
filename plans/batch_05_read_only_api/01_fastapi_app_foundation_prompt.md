# Task 01 Prompt: FastAPI App Foundation

Follow `VIBE_CODING_GUIDE.md` and `plans/batch_05_read_only_api/BATCH_05_READ_ONLY_API.md`.

## Goal

Introduce the minimal API package and FastAPI app factory for read-only adapter work.

## Scope

- Add FastAPI as a runtime dependency.
- Add `src/personality_jelly/api/` with an exported `create_app` function.
- Add a health route such as `GET /health`.
- Ensure the app factory accepts testable configuration, especially a database URL or prebuilt
  database resources.
- Reuse application bootstrap helpers where practical.
- Add focused tests that instantiate the app without starting a network server.

## Non-Goals

- Do not add read/write entity routes in this task except health.
- Do not add `uvicorn` unless a maintainer explicitly asks for a local run command.
- Do not expose config secrets, local filesystem paths, DB migration commands, or provider
  settings through health output.
- Do not change CLI behavior.

## Implementation Notes

- Prefer `personality_jelly.api.app:create_app` as the public app factory.
- Keep route registration explicit and small.
- The default app should load normal settings, but tests should be able to inject an in-memory or
  temporary SQLite database.
- If TestClient requires an additional dependency in this environment, add the smallest compatible
  dev/test dependency and update the lockfile through `uv`.

## Verification

Run focused API app tests and dependency import checks, then `git status --short --branch`.

## Completion

Commit only this task's changes on `feature/api-app-foundation`.

Do not merge this branch back into `dev`. Push only the task branch to `origin` and report the
branch name and commit hash. A coordinator or maintainer will handle review and integration into
`dev`.
