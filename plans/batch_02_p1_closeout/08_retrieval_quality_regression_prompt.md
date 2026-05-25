# Task 08 Prompt: Retrieval Quality Regression

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent baseline in `VIBE_CODING_GUIDE.md`.

## Branch

This task should start only after Task 06 Benchmark Case Assets is accepted and integrated into
`dev`.

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/retrieval-quality-regression
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task is Wave B.

Can run in parallel with:

- Task 09 OOC Regression Case Curation

Must wait for:

- Task 06 Benchmark Case Assets

Coordinate before editing `src/personality_jelly/cli/main.py`; Task 11 owns broad CLI validation diagnostics.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `plans/batch_02_p1_closeout/P1_CLOSEOUT_ORCHESTRATION.md`
- benchmark asset README from Task 06
- `src/personality_jelly/evaluation/retrieval_benchmark.py`
- `src/personality_jelly/retrieval/semantic.py`
- `tests/test_retrieval_benchmark.py`
- retrieval benchmark coverage in `tests/test_cli_demo.py`

## Goal

Harden retrieval quality regression coverage using explicit cases files and existing diagnostics.
The goal is to catch retrieval regressions, not to tune behavior blindly.

## Implementation Requirements

- Add curated retrieval cases covering at least:
  - evidence case with one expected chunk;
  - evidence case with multiple expected chunks if current fixtures support it;
  - empty-result case that should retrieve nothing;
  - missing expected chunk failure shape;
  - top result not expected when available through deterministic fixtures.
- Keep pass/fail rules unchanged:
  - evidence cases pass only when recall is `1.0` and first relevant rank is `1`;
  - empty cases pass only when retrieval returns no chunks.
- Prefer tests that use committed cases files through the existing loader.
- Do not add fixed vocabulary, regex, or string-containment semantic retrieval judgments.
- If a real behavior bug is found, first encode it as a failing regression case, then apply the
  smallest behavior fix.

## Expected Write Scope

Likely files:

- `benchmarks/retrieval/*.json`
- `tests/test_retrieval_benchmark.py`
- possibly `tests/test_cli_demo.py`
- possibly `src/personality_jelly/retrieval/semantic.py` only for a justified bug fix

Avoid editing OOC benchmark files owned by Task 09.

## Tests

Run focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests\test_retrieval_benchmark.py tests\test_cli_demo.py
```

Then run full suite if retrieval behavior or CLI behavior changes:

```powershell
.\.venv\Scripts\python -m pytest
```

## Completion

Commit only this task's changes on `feature/retrieval-quality-regression`.

Do not merge this branch back into `dev`. Push only the task branch to `origin` and report the
branch name and commit hash. A coordinator or maintainer will handle review and integration into
`dev`.

In your final report, include:

- curated retrieval cases added;
- regression scenarios covered;
- whether retrieval behavior changed;
- confirmation that pass/fail rules did not change;
- tests run and results.
