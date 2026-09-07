# Task 01 Prompt: Persona Setup Provider Trace Foundation

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_11_provider_backed_persona_setup/BATCH_11_PROVIDER_BACKED_PERSONA_SETUP.md`.

## Branch

Create an isolated implementation worktree from clean updated `dev`. Do not implement this task by
switching branches in the root checkout.

```powershell
git fetch origin
git worktree add C:\Projects\PersonalityJelly-worktrees\batch11-01-persona-setup-provider-trace -b feature/api-persona-setup-provider-trace-foundation origin/dev
Set-Location C:\Projects\PersonalityJelly-worktrees\batch11-01-persona-setup-provider-trace
```

If the coordinator provides a different worktree path or base, use that base and report it.

## Read First

- `VIBE_CODING_GUIDE.md`
- `plans/batch_11_provider_backed_persona_setup/BATCH_11_PROVIDER_BACKED_PERSONA_SETUP.md`
- `plans/batch_09_provider_backed_api_planning/02_character_persona_setup_api_contract.md`
- `plans/batch_09_provider_backed_api_planning/03_provider_backed_write_contract_matrix.md`
- `src/personality_jelly/application/providers.py`
- `src/personality_jelly/application/character_persona_setup.py`
- `src/personality_jelly/extraction/service.py`
- `src/personality_jelly/extraction/reader.py`
- `src/personality_jelly/extraction/verifier.py`
- `src/personality_jelly/persona/compiler.py`
- `src/personality_jelly/llm/tracing.py`

## Goal

Prepare the provider and trace-correlation foundation that the Batch 11 staged application workflow
will use. This task must not add an HTTP route or staged persona setup workflow.

## Expected Implementation

Add setup-specific provider/model bundle types in `personality_jelly.application.providers`, for
example:

- `PersonaSetupProviderRoleBundle`
- `PersonaSetupModelRoleBundle`
- `build_persona_setup_role_bundles(...)`
- `resolve_persona_setup_provider(...)` or an equivalent helper for `stub` and `env`

Expected behavior:

- The bundle has separate roles for `reader`, `verifier`, and `persona_compiler`.
- The first implementation supports provider sources `stub` and `env`.
- Missing role model values inherit the resolved bundle-level model.
- No raw API key, base URL, header, provider payload, prompt, or server-local config path is ever
  represented in the public bundle models.
- Existing turn role bundle behavior remains unchanged.

Add trace-correlation plumbing so Reader, Verifier, and persona compiler calls can be invoked with
step-specific trace recorders carrying:

- `request_id`
- `workflow_id`
- `workflow_step`
- safe related IDs such as `source_work_id` and `character_id`

Recommended implementation:

- Let `run_reader_extraction`, `verify_candidate_claims`, and `compile_persona_version` accept an
  optional trace recorder or trace context while preserving current default behavior.
- Use existing `RepositoryLLMTraceRecorder` support for request/workflow/step/related IDs.
- Do not change prompts, semantic behavior, benchmark pass/fail logic, or CLI behavior.
- Do not create workflow runs, audit events, idempotency records, or API schemas in this task.

## Tests

Add focused tests, suggested:

```powershell
.\.venv\Scripts\python -m pytest tests/test_persona_setup_provider_trace_foundation.py
```

Cover at least:

- setup provider/model bundles resolve separate Reader, Verifier, and persona compiler roles
- `stub` and `env` resolution paths keep existing settings behavior
- missing role model values inherit the bundle-level model
- unsupported provider source raises validation failure
- Reader, Verifier, and compiler traces can store request/workflow/step/related IDs
- existing tests that call Reader, Verifier, compiler, and `build_character_persona` still pass

Also run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_application_bootstrap.py tests/test_reader_extraction.py tests/test_canon_verifier.py tests/test_persona_compiler.py tests/test_character_persona_setup_service.py tests/test_repositories.py
```

## Non-Goals

- Do not add `POST /characters/{character_id}/persona-setup-runs`.
- Do not implement `run_character_persona_setup_workflow`.
- Do not add staged commits, workflow/audit/idempotency state, migrations, prompt edits, semantic
  behavior changes, or provider-backed route behavior.

## Completion

Run:

```powershell
git diff --check
git status --short --branch
```

Commit only Task 01 changes and push the branch. Report branch, commit hash, tests run, and any
implementation notes relevant to Task 02.
