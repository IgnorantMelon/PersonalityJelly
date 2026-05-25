# Task 02 Prompt: Inspection Result Models

Follow `VIBE_CODING_GUIDE.md`, `P2_ACCEPTANCE_CRITERIA.md`, and the Batch 04 orchestration doc.

## Goal

Define shared structured result models for read-only inspection services so CLI and future API
adapters can consume the same data.

## Scope

- Add result models for entity summaries, detail payloads, linked IDs, layered summaries, and
  benchmark diagnostics.
- Prefer dataclasses or Pydantic models consistent with existing project style.
- Keep models transport-neutral and free of CLI formatting.
- Document expansion conventions: default IDs, optional linked summaries/details.

## Non-Goals

- Do not implement all inspection services in this task.
- Do not change domain persistence models.
- Do not add HTTP request/response models.

## Verification

Add focused tests for model construction/serialization if using Pydantic. Run `git status`.
