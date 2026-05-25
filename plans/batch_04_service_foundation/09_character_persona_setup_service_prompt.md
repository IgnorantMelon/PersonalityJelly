# Task 09 Prompt: Character Persona Setup Service

Follow `VIBE_CODING_GUIDE.md`, `P2_ACCEPTANCE_CRITERIA.md`, and Batch 04 service conventions.

## Goal

Extract reusable character/persona setup sequencing while keeping the one-shot `demo` workflow and
its unsafe reuse policies CLI-only.

## Scope

- Service sequence for character/persona build from an explicit character/source context.
- Return source work, character, candidate claim IDs, evidence ref IDs, verified claim IDs,
  conflict IDs, and persona version ID.
- Keep title-based source reuse and display-name user reuse in CLI demo helpers.
- Preserve existing demo behavior and output.

## Non-Goals

- Do not add multi-work canon policies.
- Do not change Reader, Verifier, or persona compiler semantics.
- Do not turn `demo` into a public API workflow.

## Verification

Run focused demo, extraction, verifier, persona, and character service tests.
