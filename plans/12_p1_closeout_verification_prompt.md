# Task 12 Prompt: P1 Closeout Verification

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent baseline in `VIBE_CODING_GUIDE.md`.

## Branch

This task should start only after Tasks 06-11 are merged.

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c chore/p1-closeout-verification
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task is Wave D and must wait for:

- Task 06 Benchmark Case Assets
- Task 07 Layered Summary Downstream Audit
- Task 08 Retrieval Quality Regression
- Task 09 OOC Regression Case Curation
- Task 10 Trace CLI Navigation
- Task 11 CLI Validation Diagnostics

Do not start while any Wave B or Wave C branch is still unmerged.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `plans/P1_CLOSEOUT_ORCHESTRATION.md`
- final reports or merge commits for Tasks 06-11
- `README.md`
- benchmark asset README
- current CLI tests and benchmark tests

## Goal

Perform the final P1 closeout verification pass. Confirm that the project status, docs, tests, and
CLI workflows reflect the completed P1 hardening stage.

This is a verification and documentation task. Do not introduce new product behavior unless a small
fix is required to make documented P1 behavior true.

## Implementation Requirements

- Run focused checks for:
  - OOC benchmark built-in suites and cases-file flow;
  - retrieval benchmark generated and cases-file flow;
  - layered summary display and runtime context behavior;
  - LLM trace list/show inspection;
  - CLI config/db status commands.
- Run full `pytest`.
- Update `VIBE_CODING_GUIDE.md` current implemented surface, P1 backlog, and test snapshot.
- Update `README.md` only if public quick-start/status is stale.
- Do not move coding-agent instructions into `README.md`.
- Leave clear notes for the next P2 planning branch.

## Expected Write Scope

Likely files:

- `VIBE_CODING_GUIDE.md`
- possibly `README.md`
- possibly a small test/doc correction if verification finds stale behavior

Avoid editing service implementation unless verification finds a real bug.

## Tests

Run focused tests first based on changed areas, then:

```powershell
.\.venv\Scripts\python -m pytest
```

Also run useful CLI smoke checks, for example:

```powershell
.\.venv\Scripts\pjelly.exe config show
.\.venv\Scripts\pjelly.exe config check
.\.venv\Scripts\pjelly.exe db status
```

## Completion

Commit only this task's changes on `chore/p1-closeout-verification`. In your final report, include:

- P1 closeout checklist result;
- docs updated;
- tests and CLI smoke checks run;
- final full-suite result;
- recommended first P2 planning topic.
