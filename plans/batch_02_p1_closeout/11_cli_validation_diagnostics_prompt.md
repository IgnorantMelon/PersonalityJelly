# Task 11 Prompt: CLI Validation Diagnostics

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent baseline in `VIBE_CODING_GUIDE.md`.

## Branch

This task should start after Task 10 Trace CLI Navigation is accepted and integrated into `dev`.
Prefer starting after Tasks 08 and 09 are accepted and integrated so validation diagnostics cover
the final curated cases-file workflows.

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/cli-validation-diagnostics
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task is Wave C.

Must wait for:

- Task 10 Trace CLI Navigation

Prefer waiting for:

- Task 08 Retrieval Quality Regression
- Task 09 OOC Regression Case Curation

Do not run this in parallel with another task that edits `src/personality_jelly/cli/main.py`.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `plans/batch_02_p1_closeout/P1_CLOSEOUT_ORCHESTRATION.md`
- `src/personality_jelly/cli/main.py`
- `src/personality_jelly/evaluation/benchmark.py`
- `src/personality_jelly/evaluation/retrieval_benchmark.py`
- `tests/test_cli_demo.py`
- cases assets from Tasks 06, 08, and 09 if present

## Goal

Improve CLI validation and error diagnostics around benchmark cases files, export paths, provider
configuration, and batch benchmark output while preserving script-friendly output.

## Implementation Requirements

- Preserve existing command names, argument names, exit codes, and stable output fields.
- Improve error messages for cases-file validation failures where practical:
  - missing file;
  - malformed JSON;
  - duplicate case id;
  - invalid interaction mode;
  - blank required fields;
  - export path exists without overwrite/append.
- Prefer deterministic validation context such as case id or list index.
- Do not change benchmark pass/fail semantics.
- Do not add keyword or regex semantic judgments.
- If helper extraction is needed, keep helpers private to CLI or evaluation modules according to the
  existing boundary.
- Add tests for the most important error messages and exit behavior.

## Expected Write Scope

Likely files:

- `src/personality_jelly/cli/main.py`
- `src/personality_jelly/evaluation/benchmark.py`
- `src/personality_jelly/evaluation/retrieval_benchmark.py`
- `tests/test_cli_demo.py`
- possibly `tests/test_evaluation_benchmark.py`
- possibly `tests/test_retrieval_benchmark.py`

Avoid broad CLI output refactors already handled by Task 05.

## Tests

Run focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests\test_cli_demo.py tests\test_evaluation_benchmark.py tests\test_retrieval_benchmark.py
```

Then run full suite because this touches shared CLI/evaluation behavior:

```powershell
.\.venv\Scripts\python -m pytest
```

## Completion

Commit only this task's changes on `feature/cli-validation-diagnostics`.

Do not merge this branch back into `dev`. Push only the task branch to `origin` and report the
branch name and commit hash. A coordinator or maintainer will handle review and integration into
`dev`.

In your final report, include:

- diagnostics improved;
- examples of preserved output compatibility;
- tests run and results;
- any validation cases intentionally left unchanged.
