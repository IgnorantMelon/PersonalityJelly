# Task 09 Prompt: OOC Regression Case Curation

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent baseline in `VIBE_CODING_GUIDE.md`.

## Branch

This task should start only after Task 06 Benchmark Case Assets is merged.

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/ooc-regression-case-curation
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task is Wave B.

Can run in parallel with:

- Task 08 Retrieval Quality Regression

Must wait for:

- Task 06 Benchmark Case Assets

Coordinate before editing `src/personality_jelly/cli/main.py`; Task 11 owns broad CLI validation diagnostics.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `plans/P1_CLOSEOUT_ORCHESTRATION.md`
- benchmark asset README from Task 06
- `src/personality_jelly/evaluation/benchmark.py`
- `src/personality_jelly/critic/service.py`
- `tests/test_evaluation_benchmark.py`
- OOC benchmark coverage in `tests/test_cli_demo.py`

## Goal

Curate explicit OOC regression cases that represent observed-failure style boundaries without
expanding built-in suites. These cases should be run through the cases-file workflow added earlier.

## Implementation Requirements

- Add curated OOC cases covering at least:
  - canon rewrite attempts;
  - memory pollution attempts;
  - roleplay/reality mode confusion;
  - modern-world adaptation without canon rewrite;
  - meta discussion boundary review.
- Keep cases small and deterministic.
- Use explicit cases files rather than modifying built-in suites unless there is a strong reason.
- Preserve pass/fail semantics from structured `BenchmarkCaseEvaluation`.
- Add tests proving the curated file loads and can run/dry-run through the existing workflow.
- Do not use keyword, regex, or string-containment rules to judge OOC behavior.

## Expected Write Scope

Likely files:

- `benchmarks/ooc/*.json`
- `tests/test_evaluation_benchmark.py`
- possibly `tests/test_cli_demo.py`

Avoid editing retrieval benchmark files owned by Task 08.

## Tests

Run focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests\test_evaluation_benchmark.py tests\test_cli_demo.py
```

Then run full suite if shared evaluation or CLI behavior changes:

```powershell
.\.venv\Scripts\python -m pytest
```

## Completion

Commit only this task's changes on `feature/ooc-regression-case-curation`. In your final report, include:

- curated OOC cases added;
- boundary categories covered;
- confirmation that evaluator semantics did not change;
- tests run and results.
