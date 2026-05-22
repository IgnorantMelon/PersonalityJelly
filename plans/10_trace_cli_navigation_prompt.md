# Task 10 Prompt: Trace CLI Navigation

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent baseline in `VIBE_CODING_GUIDE.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/trace-cli-navigation
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task can start immediately. It is part of Wave A.

It can run in parallel with:

- Task 06 Benchmark Case Assets
- Task 07 Layered Summary Downstream Audit

Task 11 should wait for this task to be accepted and integrated into `dev` because both may touch
`src/personality_jelly/cli/main.py`.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `plans/P1_CLOSEOUT_ORCHESTRATION.md`
- `src/personality_jelly/cli/main.py`
- `src/personality_jelly/storage/repositories.py`
- `src/personality_jelly/llm/tracing.py`
- `tests/test_cli_demo.py`

## Goal

Make it easier to navigate from CLI diagnostics to related trace/context records when debugging
failed turns and benchmark runs.

This task should add read-only inspection improvements only. It must not change runtime semantics.

## Implementation Requirements

- Preserve existing command names and existing output fields.
- Prefer appending stable `key=value` fields over adding new command shapes.
- Improve at least one navigation path, such as:
  - `show llm-trace` includes enough operation/schema/model/error details to connect it to failed workflows;
  - `show eval-run` or `show retrieval-eval-run` prints related message/context/critic ids already available in stored results;
  - `show failure-case` exposes related context package and critic report ids in a way that is easy to chain.
- Do not introduce cross-table guessing by semantic text matching.
- If adding filters to `list llm-traces`, keep them explicit and deterministic.
- Keep CLI output script-friendly.

## Expected Write Scope

Likely files:

- `src/personality_jelly/cli/main.py`
- `tests/test_cli_demo.py`
- possibly repository read helpers if an explicit id relationship is missing

Avoid editing benchmark case assets.

## Tests

Run focused CLI tests:

```powershell
.\.venv\Scripts\python -m pytest tests\test_cli_demo.py
```

Then run full suite if repository or shared behavior changes:

```powershell
.\.venv\Scripts\python -m pytest
```

## Completion

Commit only this task's changes on `feature/trace-cli-navigation`.

Do not merge this branch back into `dev`. Push only the task branch to `origin` and report the
branch name and commit hash. A coordinator or maintainer will handle review and integration into
`dev`.

In your final report, include:

- new or improved navigation fields;
- confirmation that existing CLI fields were preserved;
- tests run and results;
- explicit note that Task 11 can start after this branch is accepted and integrated.
