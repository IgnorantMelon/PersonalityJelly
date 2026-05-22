# Benchmark Case Assets

This directory stores curated benchmark case files that are reviewed and committed as regression
assets. They are not generated evaluation output and should stay small enough to inspect in code
review.

## Layout

- `ooc/*.json` contains explicit OOC benchmark cases for
  `load_ooc_benchmark_cases_file`.
- `retrieval/*.json` contains explicit retrieval benchmark cases for
  `load_retrieval_benchmark_cases_file`.

## Naming

- Use lowercase kebab-case file names that describe the source or regression theme, for example
  `boundary-smoke.json` or `missing-evidence-regression.json`.
- Use stable lower_snake_case case ids, prefixed by the asset theme when practical.
- Keep prompts, queries, expected chunk ids, and limits deterministic.
- Do not commit exported run dumps, local database files, provider traces, or other generated eval
  artifacts here.

