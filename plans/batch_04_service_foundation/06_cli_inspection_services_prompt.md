# Task 06 Prompt: CLI List/Show Migration

Follow `VIBE_CODING_GUIDE.md`, `P2_ACCEPTANCE_CRITERIA.md`, and Batch 04 inspection service docs.

## Goal

Move CLI list/show command families to consume application inspection services while preserving
existing CLI output.

## Scope

- Update list/show commands for conversations, context packages, critic reports, characters,
  claims, memories, failure cases, LLM traces, OOC eval runs, and retrieval eval runs as feasible.
- Keep `_print_*` formatting helpers CLI-only.
- Preserve existing `key=value` names, ordering where practical, multiline block markers, and
  failed-only report behavior.
- Add only documented additive diagnostics.

## Non-Goals

- Do not change command semantics.
- Do not implement API handlers.
- Do not move write workflows in this task.

## Verification

Run focused CLI list/show tests and any application inspection tests touched.
