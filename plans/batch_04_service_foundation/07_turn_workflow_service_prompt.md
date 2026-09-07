# Task 07 Prompt: Turn Workflow Service

Follow `VIBE_CODING_GUIDE.md`, `P2_ACCEPTANCE_CRITERIA.md`, and Batch 04 service conventions.

## Goal

Add an application turn workflow service that wraps existing runtime behavior and returns a
structured result suitable for CLI and future API use.

## Scope

- Wrap `send_roleplay_turn` without changing runtime behavior.
- Return conversation ID, user message ID, assistant message ID, context package ID, interaction
  mode, critic report/action, retry count, rejected message/report IDs, failure case IDs, and
  created memory IDs/statuses.
- Preserve `pjelly turn` and demo turn output. Adding memory IDs is allowed only as a documented
  additive diagnostic.
- Keep provider role and model config bundle usage explicit.

## Non-Goals

- Do not change context assembly, critic behavior, memory guard behavior, or trace persistence.
- Do not add API handlers.
- Do not implement audit persistence.

## Verification

Run focused turn orchestration and CLI turn/demo tests.
