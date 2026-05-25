# Task 06 Prompt: API Contract And Docs Pass

Follow `VIBE_CODING_GUIDE.md` and `plans/batch_05_read_only_api/BATCH_05_READ_ONLY_API.md`.

## Goal

Review the completed read-only API adapter for route consistency, response stability, docs
alignment, and test coverage gaps.

## Scope

- Audit route names, tags, query params, and response models across Tasks 03-05.
- Confirm all read-only handlers call application services and do not duplicate CLI printers or
  semantic logic.
- Confirm error envelopes are consistent across endpoint families.
- Add missing API tests for route families that lack not-found, validation, or filter coverage.
- Update `README.md` and `VIBE_CODING_GUIDE.md` only if the implemented Batch 05 status needs a
  concise current-status note.
- Document any intentionally deferred endpoint or redaction concern in this batch directory.

## Non-Goals

- Do not add new endpoint families beyond Batch 05 scope.
- Do not add write endpoints.
- Do not make broad README rewrites or move agent rules out of `VIBE_CODING_GUIDE.md`.
- Do not add auth, CORS, deployment, or server process management.

## Implementation Notes

- Prefer additive tests over response-shape churn.
- Keep response changes backward-compatible within the batch unless a route is clearly wrong.
- If route handlers have started accumulating workflow logic, extract that logic back into
  `application` rather than keeping it in `api`.

## Verification

Run the full API route test set plus focused CLI inspection tests. Run full pytest if any shared
application models changed.
