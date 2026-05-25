# Task 07 Prompt: Layered Summary Downstream Audit

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent baseline in `VIBE_CODING_GUIDE.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/layered-summary-downstream-audit
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Scheduling

This task can start immediately. It is part of Wave A.

It can run in parallel with:

- Task 06 Benchmark Case Assets
- Task 10 Trace CLI Navigation

Do not edit benchmark asset files owned by Task 06.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `plans/batch_02_p1_closeout/P1_CLOSEOUT_ORCHESTRATION.md`
- `src/personality_jelly/runtime/summary.py`
- `src/personality_jelly/runtime/summary_schemas.py`
- `src/personality_jelly/runtime/context.py`
- `src/personality_jelly/runtime/turn.py`
- `src/personality_jelly/memory/curator.py`
- `tests/test_conversation_summary.py`
- `tests/test_runtime_context.py`
- `tests/test_turn_orchestration.py`

## Goal

Audit and harden downstream use of layered conversation summaries. The runtime should preserve the
boundary between short-term scene state, user memory candidates, relationship memory notes, and
reflective notes.

This task may add tests or small fixes. It should not redesign summary generation.

## Implementation Requirements

- Identify every downstream consumer of `conversation.summary` and parsed summary layers.
- Add focused tests proving:
  - short-term scene state can enter runtime context where intended;
  - user memory candidates are not treated as verified accepted memories;
  - relationship memory notes do not rewrite canon or persona fields;
  - reflective notes do not enter source evidence, canon claims, or persona compilation.
- Prefer explicit structured parsing with `parse_layered_summary`.
- If a downstream consumer needs a safer helper, keep it in the runtime/memory module boundary, not
  in CLI.
- Preserve existing CLI summary output fields.
- Do not add keyword, regex, or string-containment semantic judgments.

## Expected Write Scope

Likely files:

- `src/personality_jelly/runtime/context.py`
- `src/personality_jelly/runtime/turn.py`
- `src/personality_jelly/runtime/summary.py`
- focused tests under `tests/`

Avoid editing evaluation benchmark modules unless a test uncovers direct coupling.

## Tests

Run focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests\test_conversation_summary.py tests\test_runtime_context.py tests\test_turn_orchestration.py
```

Then run full suite if runtime behavior changes:

```powershell
.\.venv\Scripts\python -m pytest
```

## Completion

Commit only this task's changes on `feature/layered-summary-downstream-audit`.

Do not merge this branch back into `dev`. Push only the task branch to `origin` and report the
branch name and commit hash. A coordinator or maintainer will handle review and integration into
`dev`.

In your final report, include:

- downstream consumers audited;
- tests added or strengthened;
- any behavior fixes made;
- confirmation that summary layers remain separate from canon/persona data;
- tests run and results.
