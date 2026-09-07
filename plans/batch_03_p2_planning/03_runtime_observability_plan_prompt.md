# Task 03 Prompt: Runtime Workflow Observability Plan

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent
baseline in `VIBE_CODING_GUIDE.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c planning/runtime-observability
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task is Wave A and can start immediately.

It can run in parallel with:

- Task 01 FastAPI Service Boundary Design
- Task 02 Multi-Work / Multi-Character Boundary Audit

Task 05 CLI/API Shared Service Refactor Plan should wait for this task and Task 01.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `plans/batch_03_p2_planning/P2_PLANNING_ORCHESTRATION.md`
- `src/personality_jelly/runtime/turn.py`
- `src/personality_jelly/runtime/context.py`
- `src/personality_jelly/runtime/summary.py`
- `src/personality_jelly/critic/service.py`
- `src/personality_jelly/memory/curator.py`
- `src/personality_jelly/memory/guard.py`
- `src/personality_jelly/llm/tracing.py`
- `src/personality_jelly/evaluation/benchmark.py`
- `src/personality_jelly/evaluation/retrieval_benchmark.py`
- CLI trace and inspection commands in `src/personality_jelly/cli/main.py`

## Goal

Plan how a future API or UI can inspect a complete runtime workflow: user message, interaction mode,
context package, generated reply, critic report, memory curation, memory guard decision, summary
update, traces, and benchmark or failure-case records.

This is a planning task. Do not change trace persistence or runtime behavior.

## Planning Requirements

- Map the current turn workflow from input message to persisted outputs.
- List the important inspection records and their linking IDs.
- Identify where trace coverage already exists and where future trace links would be useful.
- Show how a user could navigate from:
  - a conversation turn to its context package;
  - a context package to source chunks and claims;
  - a generated response to critic report and failure case;
  - a memory write to curator and guard decisions;
  - a benchmark failed case to relevant traces or context.
- Identify observability gaps that matter for API/UI debugging.
- Preserve the current semantic judgment rules; do not propose keyword or regex judges.
- Separate must-have P2 observability from nice-to-have later platform observability.

## Expected Write Scope

Likely files:

- `plans/batch_03_p2_planning/03_runtime_observability_plan.md`

Avoid editing source code, tests, README, or `VIBE_CODING_GUIDE.md` unless a small status correction
is necessary.

## Verification

No automated tests are required for this planning task unless you make code changes.

Before completion, run:

```powershell
git status --short --branch
```

## Completion

Commit only this task's changes on `planning/runtime-observability`.

Do not merge this branch back into `dev`. Push only the task branch to `origin` and report the
branch name and commit hash. A coordinator or maintainer will handle review and integration into
`dev`.

In your final report, include:

- workflow map summary;
- linking IDs and records;
- most important observability gaps;
- P2 must-haves versus later items;
- tests or checks run.
