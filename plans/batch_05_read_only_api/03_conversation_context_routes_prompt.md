# Task 03 Prompt: Conversation And Context Routes

Follow `VIBE_CODING_GUIDE.md` and `plans/batch_05_read_only_api/BATCH_05_READ_ONLY_API.md`.

## Goal

Expose read-only HTTP endpoints for conversations and context packages over existing application
inspection services.

## Scope

- Add `GET /conversations?limit=...`.
- Add `GET /conversations/{conversation_id}`.
- Add `GET /context-packages/{context_package_id}`.
- Reuse `list_conversations`, `inspect_conversation`, and `inspect_context_package` or equivalent
  application services.
- Support existing expansion/detail options only when they are already available through
  application service parameters.
- Add route tests for success, not found, invalid limits, and context expansion behavior.

## Non-Goals

- Do not create conversations or run turns.
- Do not summarize conversations.
- Do not redact or rewrite assembled prompts in this local read-only phase.
- Do not duplicate repository assembly in route handlers.
- Do not change CLI conversation/context output.

## Implementation Notes

- Response bodies may return the application inspection models directly if FastAPI serializes them
  cleanly.
- Preserve `conversation_id`, `user_id`, `character_id`, `persona_version_id`,
  `interaction_mode`, message IDs, `context_package_id`, claim IDs, memory IDs, retrieved chunk
  IDs, and summary layers.
- Keep query filters conservative. Add only filters backed by application services.

## Verification

Run focused API conversation/context tests and existing conversation/context inspection tests.

## Completion

Commit only this task's changes on `feature/api-conversation-context`.

Do not merge this branch back into `dev`. Push only the task branch to `origin` and report the
branch name and commit hash. A coordinator or maintainer will handle review and integration into
`dev`.
