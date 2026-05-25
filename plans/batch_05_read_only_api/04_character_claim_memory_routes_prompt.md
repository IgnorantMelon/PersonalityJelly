# Task 04 Prompt: Character, Claim, Memory, And Source Routes

Follow `VIBE_CODING_GUIDE.md` and `plans/batch_05_read_only_api/BATCH_05_READ_ONLY_API.md`.

## Goal

Expose read-only HTTP endpoints for character canon, evidence, memories, and source chunks.

## Scope

- Add `GET /characters?source_work_id=...`.
- Add `GET /characters/{character_id}`.
- Add `GET /claims?character_id=...&status=...&claim_type=...`.
- Add `GET /claims/{claim_id}`.
- Add `GET /memories?user_id=...&character_id=...&scope=...&status=...`.
- Add `GET /memories/{memory_id}`.
- Add `GET /source-chunks/{chunk_id}`.
- Reuse application inspection services for all record assembly.
- If character listing is not yet exposed through `application`, add a small read-only application
  helper before wiring the route.
- Add tests for filtering, enum validation, evidence/chunk expansion, not found, and invalid
  query values.

## Non-Goals

- Do not add character creation, extraction, verification, persona compilation, memory review,
  memory edit, memory archive, or audit persistence routes.
- Do not add global character lookup by display name or canonical name.
- Do not merge user memory and relationship memory in response models.
- Do not add semantic checks in API code.

## Implementation Notes

- Preserve distinct `source_work_id`, `character_id`, `claim_id`, `evidence_id`, `chunk_id`,
  `user_id`, `conversation_id`, `memory_scope`, and `memory_status` fields.
- Let Pydantic/FastAPI enum validation reject invalid `status`, `claim_type`, and `scope` values.
- Do not expose local source file paths. Source chunk text is acceptable because source chunk
  inspection already exists locally.

## Verification

Run focused API character/claim/memory/source route tests and existing application inspection
tests.
