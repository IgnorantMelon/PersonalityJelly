# Task 02 Prompt: Layered Summary Context Consumption

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent baseline in `VIBE_CODING_GUIDE.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/layered-summary-context
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `src/personality_jelly/runtime/summary.py`
- `src/personality_jelly/runtime/context.py`
- `tests/test_conversation_summary.py`
- `tests/test_runtime_context.py`

## Goal

Make runtime context assembly consume layered conversation summaries as structured layers instead of passing the whole stored summary as one undifferentiated block.

This should improve prompt clarity while preserving current storage format and backwards compatibility.

## Implementation Requirements

- In context assembly, parse `conversation.summary` with `parse_layered_summary`.
- Keep the existing `# Conversation Summary` prompt heading.
- Under that heading, render these stable subsections:
  - `short_term_scene_state`
  - `user_memory_candidates`
  - `relationship_memory_notes`
  - `reflective_notes`
- For empty lists, render `- none` using the existing prompt style.
- For legacy unlayered summaries, treat the legacy text as `short_term_scene_state` and keep other sections empty.
- Do not automatically promote summary user memory candidates into persisted `Memory` rows.
- Do not change the stored `Conversation.summary` schema or database schema.

## Expected Write Scope

Likely files:

- `src/personality_jelly/runtime/context.py`
- `tests/test_runtime_context.py`
- maybe `tests/test_conversation_summary.py` if a parser edge case needs coverage

Avoid editing CLI files. CLI already parses and prints summary layers.

## Tests

Add or update tests that prove:

- assembled context prompt includes each layered summary subsection;
- user memory candidates and relationship notes are displayed as context only;
- legacy unlayered summary remains available as short-term scene state;
- empty summary still renders a clear `none` state;
- no new `Memory` rows are created by context assembly.

Run focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests\test_runtime_context.py tests\test_conversation_summary.py
```

Run full suite if shared behavior changed beyond context formatting:

```powershell
.\.venv\Scripts\python -m pytest
```

## Completion

Commit only this task's changes on `feature/layered-summary-context`. In your final report, include:

- files changed;
- before/after prompt shape summary;
- tests run and results.
