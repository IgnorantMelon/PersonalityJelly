# Task 10 Prompt: Audit Readiness

Follow `VIBE_CODING_GUIDE.md`, `P2_ACCEPTANCE_CRITERIA.md`, and Task 04 user/workspace/audit
decisions.

## Goal

Decide and, if accepted for Batch 04, implement the minimum audit readiness needed before manual
memory operations become API/UI-facing.

## Scope

- Define audit payload models for actor, operation, entity, reason, related IDs, before/after
  state, and metadata.
- Decide whether Batch 04 should add a physical audit table or keep payloads design-only.
- If implementing persistence, keep it append-only and focused on manual memory review/edit/archive.
- Require archive reason if moving archive into audited application service behavior.

## Non-Goals

- Do not implement workspace, auth, permissions, billing, or compliance exports.
- Do not make audit records the source of domain state.
- Do not audit every domain transition in this task.

## Verification

If docs only, run `git status`. If code/migration is added, run focused tests and the full suite.
