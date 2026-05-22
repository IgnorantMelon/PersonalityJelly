# Task 05 Prompt: CLI Diagnostics Helper Refactor

You are one agent in a multi-agent development run for Personality Jelly. You are not alone in the codebase. Do not revert, rewrite, or reformat work from other agents. Keep your edits tightly scoped to this task, and leave unrelated files alone.

## Branch

This task should run after the retrieval diagnostics and OOC cases-file branches are merged, because it intentionally touches shared CLI benchmark output code.

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c refactor/cli-diagnostics-helpers
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Read First

Read these before editing:

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `src/personality_jelly/cli/main.py`
- `tests/test_cli_demo.py`
- current benchmark modules in `src/personality_jelly/evaluation/`

Follow the current P1 hardening direction. Do not add FastAPI, platform features, graph/vector databases, LangGraph, or new dependencies.

## Goal

Reduce duplication and risk in CLI diagnostics printing after P1 benchmark enhancements, while preserving existing script-friendly CLI output.

This is a refactor task. It should not change product behavior.

## Implementation Requirements

- Extract small internal helpers for repeated benchmark summary, cases summary, and verbose case output patterns.
- Keep helpers private to the CLI module unless there is a clear existing module boundary that fits better.
- Preserve all existing CLI command names, argument names, exit codes, and output field names.
- Existing fields must not be renamed, removed, reordered in risky ways, or reformatted.
- New helper names should describe output shape, not business policy.
- Do not move reusable service behavior into CLI. CLI remains orchestration and human-readable diagnostics only.
- Do not introduce keyword, regex, or fixed-vocabulary semantic judgments.
- Do not add dependencies.

## Expected Write Scope

Likely files:

- `src/personality_jelly/cli/main.py`
- `tests/test_cli_demo.py` only if output-preservation tests need tightening

Avoid editing evaluation modules unless a helper boundary clearly belongs there and tests justify it.

## Tests

Add or update tests only where needed to lock important output compatibility.

Run focused CLI tests:

```powershell
.\.venv\Scripts\python -m pytest tests\test_cli_demo.py
```

Then run full suite:

```powershell
.\.venv\Scripts\python -m pytest
```

## Completion

Commit only this task's changes on `refactor/cli-diagnostics-helpers`. In your final report, include:

- files changed;
- helpers extracted;
- confirmation that CLI output compatibility was preserved;
- tests run and results.
