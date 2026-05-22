# Task 03 Prompt: Retrieval Benchmark Diagnostics

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent baseline in `VIBE_CODING_GUIDE.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/retrieval-benchmark-diagnostics
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `src/personality_jelly/evaluation/retrieval_benchmark.py`
- retrieval benchmark CLI sections in `src/personality_jelly/cli/main.py`
- `tests/test_retrieval_benchmark.py`
- retrieval benchmark coverage in `tests/test_cli_demo.py`

## Goal

Improve retrieval benchmark diagnostics so failures are easier to inspect and convert into curated cases, without changing retrieval quality semantics.

## Implementation Requirements

- Keep pass/fail rules unchanged:
  - evidence cases pass only when recall is `1.0` and first relevant rank is `1`;
  - empty cases pass only when retrieval returns no chunks.
- Add clearer deterministic diagnostics to each case result, such as:
  - expected count;
  - retrieved count;
  - top retrieved chunk id, or `none`;
  - missing expected chunk ids;
  - whether the top-ranked chunk was expected.
- Add stable CLI `key=value` fields in retrieval benchmark verbose/show output.
- Preserve all existing CLI output fields. Only append new fields.
- Do not change database schema unless there is no other way. Prefer deriving new CLI fields from existing stored result data.

## Expected Write Scope

Likely files:

- `src/personality_jelly/evaluation/retrieval_benchmark.py`
- retrieval benchmark output helpers in `src/personality_jelly/cli/main.py`
- `tests/test_retrieval_benchmark.py`
- retrieval benchmark CLI tests in `tests/test_cli_demo.py`

Coordinate carefully with agents working on OOC benchmark or CLI refactor tasks because those may also touch `cli/main.py`.

## Tests

Add or update tests that prove:

- case result reasons contain the new diagnostics for failed evidence cases;
- empty case diagnostics remain clear;
- CLI `eval retrieval-benchmark --verbose` prints new fields;
- CLI `show retrieval-eval-run` prints new fields;
- existing retrieval benchmark report fields are unchanged.

Run focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests\test_retrieval_benchmark.py tests\test_cli_demo.py
```

Then run the full suite if `cli/main.py` or shared evaluation behavior changed:

```powershell
.\.venv\Scripts\python -m pytest
```

## Completion

Commit only this task's changes on `feature/retrieval-benchmark-diagnostics`. In your final report, include:

- files changed;
- new output fields;
- confirmation that pass/fail rules did not change;
- tests run and results.
