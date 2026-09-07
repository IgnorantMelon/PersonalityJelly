# Task 03 Prompt: Conversation And Context Inspection

Follow `VIBE_CODING_GUIDE.md`, `P2_ACCEPTANCE_CRITERIA.md`, and Batch 04 result conventions.

## Goal

Implement read-only application services for conversation and context package inspection.

## Scope

- Conversation detail: conversation IDs, user, character, persona version, current mode, parsed
  summary layers, and recent messages.
- Message detail: role, content, timestamps, assistant `context_package_id`.
- Context package detail: interaction mode, persona version, claim IDs, memory IDs,
  retrieved chunk IDs, assembled prompt.
- Optional expansion for persona metadata, claim/evidence/source chunk details, memory summaries,
  and retrieved chunk locations.

## Non-Goals

- Do not change runtime context assembly.
- Do not redact prompts yet.
- Do not add API handlers.

## Verification

Add application service tests and focused CLI conversation/context tests if CLI is touched.
