# Task 04 Prompt: Character Claim Memory Inspection

Follow `VIBE_CODING_GUIDE.md`, `P2_ACCEPTANCE_CRITERIA.md`, and Batch 04 result conventions.

## Goal

Implement read-only application services for character, claim/evidence, source chunk, and memory
inspection.

## Scope

- Character detail with source work ID, aliases, latest persona summary, claim counts, and evidence
  counts.
- Claim list/detail with evidence ref IDs, chunk IDs, excerpts, and support scores.
- Memory list/detail filtered by `user_id`, `character_id`, scope, and status.
- Distinguish user memory and relationship memory in structured results.

## Non-Goals

- Do not add source-work management UI/API.
- Do not implement memory edit/review/archive audit in this task.
- Do not change memory curation or guard behavior.

## Verification

Add application service tests and focused CLI character/claim/memory tests if CLI is touched.
