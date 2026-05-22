# Task 06 Prompt: Benchmark Case Assets

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent baseline in `VIBE_CODING_GUIDE.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/benchmark-case-assets
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task can start immediately. It is part of Wave A and unblocks Tasks 08 and 09.

It can run in parallel with:

- Task 07 Layered Summary Downstream Audit
- Task 10 Trace CLI Navigation

Avoid editing `src/personality_jelly/cli/main.py` unless a focused test proves it is necessary.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `plans/P1_CLOSEOUT_ORCHESTRATION.md`
- `src/personality_jelly/evaluation/benchmark.py`
- `src/personality_jelly/evaluation/retrieval_benchmark.py`
- `tests/test_evaluation_benchmark.py`
- `tests/test_retrieval_benchmark.py`
- OOC/retrieval CLI tests in `tests/test_cli_demo.py`

## Goal

Create a small, explicit, source-controlled benchmark cases asset structure for curated regression
cases. The asset structure should support future OOC and retrieval observed-failure cases without
editing built-in suites.

This task is mostly structure, examples, and loader/export compatibility. It should not change
benchmark pass/fail semantics.

## Implementation Requirements

- Add a clear directory for curated benchmark assets, for example:
  - `benchmarks/ooc/*.json`
  - `benchmarks/retrieval/*.json`
- Add at least one minimal valid OOC cases file and one minimal valid retrieval cases file.
- Keep sample cases deterministic and small.
- Document naming conventions in a short README in the asset directory.
- Ensure existing cases-file loaders accept the committed assets.
- Add focused tests that load the committed sample files through existing loader functions.
- Do not add generated eval run output or local database artifacts.
- Do not change built-in suites unless a test proves a compatibility issue.

## Expected Write Scope

Likely files:

- `benchmarks/README.md`
- `benchmarks/ooc/*.json`
- `benchmarks/retrieval/*.json`
- `tests/test_evaluation_benchmark.py`
- `tests/test_retrieval_benchmark.py`

Avoid editing runtime, storage, and CLI modules.

## Tests

Run focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests\test_evaluation_benchmark.py tests\test_retrieval_benchmark.py
```

Run full suite if shared evaluation code changes:

```powershell
.\.venv\Scripts\python -m pytest
```

## Completion

Commit only this task's changes on `feature/benchmark-case-assets`. In your final report, include:

- asset directories and files added;
- naming conventions chosen;
- confirmation that benchmark semantics did not change;
- tests run and results;
- explicit note that Tasks 08 and 09 are unblocked after this merges.
