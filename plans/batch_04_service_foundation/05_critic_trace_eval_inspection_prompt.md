# Task 05 Prompt: Critic, Trace, And Evaluation Inspection

Follow `VIBE_CODING_GUIDE.md`, `P2_ACCEPTANCE_CRITERIA.md`, and Batch 04 result conventions.

## Goal

Implement read-only application services for critic reports, failure cases, LLM traces, OOC eval
runs, and retrieval eval runs.

## Scope

- Critic report detail by ID.
- Failure case list/detail by conversation/category and direct ID.
- LLM trace list/detail with existing filters.
- OOC eval run detail with failed-only filtering, case reasons, assistant message/context package
  links, and critic report IDs.
- Retrieval eval run detail with failed-only filtering, expected/retrieved chunk IDs, ranking
  diagnostics, and source chunk details where practical.

## Non-Goals

- Do not change trace persistence.
- Do not add workflow correlation IDs in this task.
- Do not move cases-file import/export from CLI yet.

## Verification

Add application service tests and focused CLI trace/eval tests if CLI is touched.
