# Task 01 Prompt: LLM Trace Coverage

You are one agent in a multi-agent development run for Personality Jelly. Follow the coding-agent baseline in `VIBE_CODING_GUIDE.md`.

## Branch

Start from the latest `dev` and create:

```powershell
git switch dev
git status --short --branch
git switch -c feature/llm-trace-coverage
```

If the branch already exists, inspect it and continue only if it is clearly your task branch.

## Read First

Read these before editing:

- `VIBE_CODING_GUIDE.md`
- `src/personality_jelly/llm/tracing.py`
- existing traced workflows in `runtime/mode.py`, `memory/guard.py`, and `evaluation/benchmark.py`

## Goal

Extend persisted structured LLM tracing to all important existing structured `generate_json` workflows that currently lack trace records.

Add trace coverage for:

- conversation summary generation
- critic evaluation
- memory curator extraction
- reader extraction
- verifier validation
- persona compilation

Do not change the semantic behavior of these workflows.

## Implementation Requirements

- Use the existing `record_structured_output` helper and `RepositoryLLMTraceRecorder`.
- On successful validation, persist raw output, parsed output, schema, provider name, model name, operation, and schema name.
- On Pydantic validation failure, persist raw output plus validation errors, then re-raise the original validation error.
- Keep operation names stable:
  - `runtime.summary.conversation_summary`
  - `critic.evaluate_message`
  - `memory.curator.extract_candidates`
  - `extraction.reader.extract_candidate_claims`
  - `extraction.verifier.verify_claim`
  - `persona.compile_version`
- Keep schema names equal to the Pydantic schema class names.
- Fake providers in tests must branch by schema title when one fake provider handles multiple structured tasks.

## Expected Write Scope

Likely files:

- `src/personality_jelly/runtime/summary.py`
- `src/personality_jelly/critic/service.py`
- `src/personality_jelly/memory/curator.py`
- `src/personality_jelly/extraction/reader.py`
- `src/personality_jelly/extraction/verifier.py`
- `src/personality_jelly/persona/compiler.py`
- focused tests under `tests/`

Avoid editing `cli/main.py` unless a test proves it is necessary. The existing `list llm-traces` and `show llm-trace` commands should work without CLI shape changes.

## Tests

Add or update tests that prove:

- each newly traced workflow records one successful trace with expected operation, schema name, model name, and parsed output;
- validation failures record validation errors and still raise;
- existing trace CLI inspection can list/show the new operations through the existing repository data.

Run focused tests first:

```powershell
.\.venv\Scripts\python -m pytest tests\test_conversation_summary.py tests\test_critic_service.py tests\test_memory_curator.py tests\test_reader_extraction.py tests\test_canon_verifier.py tests\test_persona_compiler.py
```

Then run the full suite:

```powershell
.\.venv\Scripts\python -m pytest
```

## Completion

Commit only this task's changes on `feature/llm-trace-coverage`. In your final report, include:

- files changed;
- tests run and results;
- any intentionally untraced structured workflow you found and why it was left out.
