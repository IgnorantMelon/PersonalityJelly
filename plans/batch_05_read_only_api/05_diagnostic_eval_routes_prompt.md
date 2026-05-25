# Task 05 Prompt: Diagnostic And Eval Routes

Follow `VIBE_CODING_GUIDE.md` and `plans/batch_05_read_only_api/BATCH_05_READ_ONLY_API.md`.

## Goal

Expose read-only HTTP endpoints for critic reports, failure cases, LLM traces, OOC eval runs, and
retrieval eval runs.

## Scope

- Add `GET /critic-reports/{critic_report_id}`.
- Add `GET /failure-cases?conversation_id=...&category=...&limit=...`.
- Add `GET /failure-cases/{failure_case_id}`.
- Add `GET /llm-traces?operation=...&schema_name=...&provider_name=...&model_name=...&with_errors=...&limit=...`.
- Add `GET /llm-traces/{trace_id}`.
- Add `GET /eval-runs?character_id=...&test_suite=...&limit=...`.
- Add `GET /eval-runs/{run_id}?failed_only=...`.
- Add `GET /retrieval-eval-runs?character_id=...&source_work_id=...&test_suite=...&limit=...`.
- Add `GET /retrieval-eval-runs/{run_id}?failed_only=...&include_chunks=...`.
- Reuse application inspection services and diagnostics models.
- Add tests for filtering, failed-only behavior, retrieval chunk inclusion, not found, and invalid
  limits.

## Non-Goals

- Do not run OOC or retrieval benchmarks through HTTP.
- Do not export cases files through HTTP.
- Do not reinterpret benchmark pass/fail, critic risk, or trace errors in handlers.
- Do not expose config diagnostics, database migration commands, or local filesystem paths.

## Implementation Notes

- Keep OOC eval and retrieval eval route families separate.
- Preserve stored `critic_report_id`, `failure_case_id`, `llm_trace_id`, `evaluation_run_id`,
  `evaluation_case_result_id`, `retrieval_evaluation_run_id`, and source chunk IDs.
- Failed-only diagnostics should match the displayed case subset, consistent with current CLI
  behavior.
- Raw LLM outputs are acceptable in this local read-only phase because CLI trace detail already
  exposes them. Defer redaction/access control to later auth/workspace work.

## Verification

Run focused API diagnostic/eval tests and existing application benchmark/inspection tests.
