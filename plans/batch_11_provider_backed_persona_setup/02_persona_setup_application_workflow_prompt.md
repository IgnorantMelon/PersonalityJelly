# Task 02 Prompt: Persona Setup Application Workflow

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_11_provider_backed_persona_setup/BATCH_11_PROVIDER_BACKED_PERSONA_SETUP.md`.

## Branch

Create an isolated implementation worktree from the completed and pushed Task 01 branch. Do not
implement this task by switching branches in the root checkout.

```powershell
git fetch origin
git worktree add C:\Projects\PersonalityJelly-worktrees\batch11-02-persona-setup-application -b feature/api-persona-setup-application-workflow origin/feature/api-persona-setup-provider-trace-foundation
Set-Location C:\Projects\PersonalityJelly-worktrees\batch11-02-persona-setup-application
```

If the coordinator provides a merged or integration base, use that base and report it.

## Read First

- `plans/batch_11_provider_backed_persona_setup/BATCH_11_PROVIDER_BACKED_PERSONA_SETUP.md`
- `plans/batch_09_provider_backed_api_planning/02_character_persona_setup_api_contract.md`
- `plans/batch_09_provider_backed_api_planning/03_provider_backed_write_contract_matrix.md`
- Task 01 implementation and tests
- `src/personality_jelly/application/character_persona_setup.py`
- `src/personality_jelly/application/correlation.py`
- `src/personality_jelly/application/audit.py`
- `src/personality_jelly/application/errors.py`
- `src/personality_jelly/application/idempotency.py`
- `src/personality_jelly/storage/repositories.py`

## Goal

Implement the transport-neutral staged application workflow for provider-backed persona setup. This
task must not add an API route.

## Expected Implementation

Add or harden public application boundary:

- `CHARACTER_PERSONA_SETUP_WORKFLOW_TYPE = "character_persona.setup"`
- step constants for `setup_preflight`, `reader_extract`, `verifier_validate`, `persona_compile`,
  `terminal_audit`, and `idempotency_record`
- `CharacterPersonaSetupWorkflowRequest`
- `CharacterPersonaSetupWorkflowResult`
- `CharacterPersonaSetupPersistedIds`
- `CharacterPersonaSetupReplay`
- `run_character_persona_setup_workflow(session, request)`

Request fields:

- `source_work_id` required
- `character_id` required
- setup provider/model bundles from Task 01 required
- `actor` required
- `correlation` required
- `idempotency` required
- optional replay payload/status wrapper so a later API route can store exact terminal replay
- `max_chunks` optional; validate as positive integer when supplied
- sanitized client `metadata` optional

Preflight rules:

- Missing source work or character is `not_found`.
- Character/source mismatch is `422 validation_error`.
- Missing actor, missing idempotency, invalid provider bundle, invalid `max_chunks`, forbidden
  metadata, provider config, paths, prompts, source text, or secrets are validation failures.
- Start the persisted workflow only after request/idempotency validation succeeds.

Staged transaction policy:

1. Persist running workflow and input links for source work and character.
2. Call Reader with step-correlated trace recorder.
3. Commit candidate claims, evidence refs, Reader trace links, and workflow links.
4. Call Verifier with step-correlated trace recorder.
5. Commit claim status updates, conflicts, Verifier trace links, and workflow links.
6. If no verified claims remain and `require_verified_claims=true`, mark workflow partial and store
   a redacted partial replay; do not compile persona.
7. Call persona compiler with step-correlated trace recorder.
8. Commit persona version, terminal audit event, workflow completion, workflow links, and
   idempotency replay together.

Failure rules:

- Provider transport failure before business rows: workflow `failed`, top-level family
  `provider_failure`.
- Provider schema/semantic validation failure before business rows: workflow `failed`, top-level
  family `provider_validation_error`.
- Any provider/validation/no-verified/compiler failure after claims/evidence or verification rows:
  workflow `partial`, top-level family `partial_persistence`.
- Partial outcomes include `failed_step`, `persisted_ids`, `llm_trace_ids`, `audit_event_ids`, and
  retry hint.
- Do not delete, merge, overwrite, or auto-repair partially persisted canon rows.
- Same idempotency key and same request hash must replay success, failed, or partial terminal
  payload without provider calls or duplicate rows.
- Same idempotency key with different request hash raises `ConflictError`.

Result requirements:

- Success result includes source work ID, character ID, candidate claim IDs, evidence ref IDs,
  verified claim IDs, conflict IDs, persona version ID, LLM trace IDs, audit event IDs, workflow
  ID, request ID, and redaction flags.
- Failed/partial results or errors contain only safe IDs/counts/statuses. No raw source text,
  evidence excerpts, prompts, provider payloads, raw outputs, provider config, paths, secrets,
  stack traces, or SQL.
- Use workflow links as the authoritative many-ID source unless expanding `WorkflowRelatedIds` is
  intentionally simpler and fully tested.

## Tests

Add focused application tests, suggested:

```powershell
.\.venv\Scripts\python -m pytest tests/test_application_character_persona_setup_workflow.py
```

Cover at least:

- successful setup persists claims, evidence, verified claims, conflicts, persona version, traces,
  workflow links, audit event, and idempotency replay
- Reader transport failure before claims marks workflow failed and creates no canon/persona rows
- Reader validation failure with trace returns safe trace IDs and no raw output
- Verifier validation failure after Reader persistence marks workflow partial
- no verified claims after Verifier marks workflow partial and does not compile persona
- compiler validation failure after verification marks workflow partial
- terminal replay for success returns stored payload without provider calls or duplicate rows
- terminal replay for partial returns stored partial payload without resuming
- idempotency hash mismatch returns conflict
- source/character mismatch and invalid actor/provider/options persist no business rows
- audit/workflow/trace/idempotency payloads are recursively redacted

Also run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_character_persona_setup_service.py tests/test_application_provider_failure_contracts.py tests/test_application_audit_workflow_inspection.py tests/test_application_idempotency.py tests/test_repositories.py
```

## Non-Goals

- Do not add an HTTP route.
- Do not add async queues, resume/repair/cleanup routes, migrations, prompt edits, semantic
  behavior changes, turn/summary/benchmark routes, or platform/auth/workspace behavior.
- Do not combine source ingest, character creation, and persona setup into one workflow.

## Completion

Run:

```powershell
git diff --check
git status --short --branch
```

Commit only Task 02 changes and push the branch. Report branch, commit hash, tests run, workflow
scope, and implementation notes relevant to Task 03.
