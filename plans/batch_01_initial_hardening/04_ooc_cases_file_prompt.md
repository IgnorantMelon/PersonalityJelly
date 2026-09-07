# Task 04 Prompt: OOC Benchmark Cases File

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent baseline in `VIBE_CODING_GUIDE.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/ooc-cases-file
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `src/personality_jelly/evaluation/benchmark.py`
- OOC benchmark CLI sections in `src/personality_jelly/cli/main.py`
- `tests/test_evaluation_benchmark.py`
- OOC benchmark coverage in `tests/test_cli_demo.py`
- retrieval cases-file implementation in `src/personality_jelly/evaluation/retrieval_benchmark.py`

## Goal

Add explicit JSON cases-file support to OOC benchmark workflows, matching the retrieval benchmark curation workflow where practical.

This lets observed OOC failures become curated regression cases without editing built-in suites.

## Public CLI Behavior

Add these capabilities:

- `pjelly eval ooc-benchmark --cases-file <path>`
- `pjelly eval ooc-benchmark --dry-run --cases-file <path>`
- `pjelly show eval-run <run_id> --failed-only --export-cases-file <path>`

Preserve existing OOC benchmark suite behavior:

- `mvp_default`
- `expanded_boundaries`
- `boundary_regression`

If `--cases-file` is supplied, use the explicit cases instead of a built-in suite. Keep `test_suite` as the user-supplied suite label unless the current CLI pattern already implies another value.

## Cases File Shape

Use this JSON shape:

```json
{
  "cases": [
    {
      "id": "manual_ooc_probe",
      "prompt": "User-facing prompt text.",
      "interaction_mode": "reality_chat",
      "category": "ooc"
    }
  ]
}
```

Validation rules:

- `cases` must contain at least one case.
- `id`, `prompt`, `interaction_mode`, and `category` are required and non-blank.
- `interaction_mode` must be one of the current `InteractionMode` enum values.
- duplicate case ids are rejected.
- unknown extra fields are rejected.

## Implementation Requirements

- Reuse the retrieval cases-file pattern for Pydantic validation, friendly `ValueError` messages, export, append, overwrite if appropriate.
- Dry-run should not call the provider and should print case distribution diagnostics.
- Failed-only export should export only displayed failed cases.
- Exported cases should preserve original prompt, interaction mode, and category.
- Do not change OOC pass/fail semantics. Pass/fail still comes from `BenchmarkCaseEvaluation`.
- Avoid database schema changes.

## Expected Write Scope

Likely files:

- `src/personality_jelly/evaluation/benchmark.py`
- OOC benchmark CLI sections in `src/personality_jelly/cli/main.py`
- `tests/test_evaluation_benchmark.py`
- OOC benchmark CLI tests in `tests/test_cli_demo.py`

Coordinate carefully with agents working on retrieval diagnostics or CLI refactor tasks because those may also touch `cli/main.py`.

## Tests

Add or update tests that prove:

- OOC cases file loads and normalizes valid cases;
- duplicate ids, empty cases, bad interaction modes, and extra fields are rejected;
- dry-run with `--cases-file` prints distribution and does not create an eval run;
- formal run with `--cases-file` executes explicit cases;
- `show eval-run --failed-only --export-cases-file` exports only failed cases;
- built-in suites still work.

Run focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests\test_evaluation_benchmark.py tests\test_cli_demo.py
```

Then run the full suite if `cli/main.py` or shared evaluation behavior changed:

```powershell
.\.venv\Scripts\python -m pytest
```

## Completion

Commit only this task's changes on `feature/ooc-cases-file`. In your final report, include:

- files changed;
- exact JSON cases-file shape;
- new CLI examples;
- tests run and results.
