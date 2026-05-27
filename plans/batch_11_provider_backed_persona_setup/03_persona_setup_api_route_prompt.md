# Task 03 Prompt: Persona Setup API Route

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_11_provider_backed_persona_setup/BATCH_11_PROVIDER_BACKED_PERSONA_SETUP.md`.

## Branch

Create an isolated implementation worktree from the completed and pushed Task 02 branch. Do not
implement this task by switching branches in the root checkout.

```powershell
git fetch origin
git worktree add C:\Projects\PersonalityJelly-worktrees\batch11-03-persona-setup-route -b feature/api-persona-setup-route origin/feature/api-persona-setup-application-workflow
Set-Location C:\Projects\PersonalityJelly-worktrees\batch11-03-persona-setup-route
```

If the coordinator provides a merged or integration base, use that base and report it.

## Read First

- `plans/batch_11_provider_backed_persona_setup/BATCH_11_PROVIDER_BACKED_PERSONA_SETUP.md`
- `plans/batch_09_provider_backed_api_planning/02_character_persona_setup_api_contract.md`
- `plans/batch_09_provider_backed_api_planning/03_provider_backed_write_contract_matrix.md`
- Task 01 and Task 02 implementations/tests
- `src/personality_jelly/api/app.py`
- `src/personality_jelly/api/routes/characters.py`
- `src/personality_jelly/api/schemas.py`
- `src/personality_jelly/api/errors.py`
- `src/personality_jelly/api/redaction.py`

## Goal

Expose the Task 02 staged application workflow through a thin FastAPI adapter:

- `POST /characters/{character_id}/persona-setup-runs`

This task must not add source ingest, character create, combined setup, turn, summary, benchmark,
auth/workspace, or UI routes.

## Expected Implementation

Add request/response schemas in the existing API style, suggested:

- `src/personality_jelly/api/persona_setup_schemas.py`
- focused additions to `src/personality_jelly/api/routes/characters.py`, or a dedicated route
  module if that matches the current app registration style

Request requirements:

- Path `character_id` is authoritative.
- Header `Idempotency-Key` is required.
- Optional body `idempotency_key` must match the header.
- Optional `X-Request-ID` must match body `request_id` when both are supplied.
- Required body fields: `source_work_id`, `provider`, `actor`.
- Optional body fields: `request_id`, `idempotency_key`, `workflow_options`, `metadata`.
- Body must not contain a different `character_id`.
- First provider source values: `stub`, `env`.
- First workflow option: optional `max_chunks`; reject unsupported workflow options.
- Reject raw API keys, bearer tokens, base URLs, headers, provider request payloads, prompts,
  source text, evidence excerpts, raw outputs, local paths, file references, URL fetches,
  provider config, prompt controls, and raw secret fields.

Response requirements:

- HTTP `201 Created` for completed setup.
- Same idempotency key and same request hash replays stored success, failed, or partial terminal
  payload without provider calls.
- Same key and different request hash returns `409 conflict`.
- Use the existing write envelope style: `request_id`, `workflow_id`, `workflow_type`, `status`,
  `ids`, `result`, `warnings`.
- `workflow_type` is `character_persona.setup`.
- `ids.source_work_id`, `ids.character_id`, `ids.persona_version_id` on success,
  `ids.audit_event_ids`, and `ids.llm_trace_ids` are populated when available.
- `result.persisted_ids` carries candidate claim IDs, evidence ref IDs, verified claim IDs,
  conflict IDs, persona version ID, trace IDs, audit IDs, and idempotency record ID when available.
- Default response returns IDs/counts/statuses/redaction booleans only.

Error mapping:

- `404 not_found`: missing source work or character.
- `409 conflict`: idempotency hash mismatch or accepted state conflict.
- `422 validation_error`: missing idempotency key, header/body mismatch, source mismatch, invalid
  actor/provider/options, forbidden fields, no candidate claims before business rows if the
  application reports that state.
- `502 provider_failure`: provider transport failure before business rows.
- `502 provider_validation_error`: provider schema/semantic validation failure before business rows.
- `500 partial_persistence`: provider/validation/no-verified/compiler failure after business rows.
- `500 unexpected_error`: sanitized defects.

Error envelopes must include safe request/workflow correlation, failed step, persisted IDs, trace
IDs, audit IDs, and retry hint when available. They must not include raw provider payloads, prompts,
source text, evidence excerpts, raw persona rules, raw outputs, stack traces, SQL, paths, secrets,
or provider config.

## Tests

Add focused API tests, suggested:

```powershell
.\.venv\Scripts\python -m pytest tests/test_api_character_persona_setup_route.py
```

Cover at least:

- successful setup after `POST /source-works` and `POST /characters` returns `201`
- generated request ID when omitted
- missing `Idempotency-Key` returns `422 validation_error`
- body/header idempotency mismatch returns `422 validation_error`
- same key and same body replays without provider calls or duplicate rows
- same key and different body returns `409 conflict`
- missing character or source returns `404 not_found`
- source/character mismatch returns `422 validation_error`
- provider failure before business rows returns sanitized provider error
- partial persistence after Reader/Verifier rows returns sanitized `partial_persistence`
- diagnostics routes inspect workflow/audit/trace records without raw source text or provider
  payloads
- OpenAPI schema exposes only safe default request/response fields

Also run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_api_contract.py tests/test_api_correlation_error_envelope.py tests/test_api_audit_workflow_inspection.py tests/test_api_diagnostics.py
```

## Non-Goals

- Do not implement combined source/character/persona convenience routes.
- Do not implement resume, repair, cleanup, deduplication, async queue, or polling routes.
- Do not add uploads, URL fetches, embeddings/source enrichment, turn execution, summary,
  benchmark, auth/workspace/platform, CORS, deployment, UI, or migrations.
- Do not expose raw provider config, raw prompts, provider payloads, source text, evidence excerpts,
  raw outputs, or debug-only payloads.

## Completion

Run:

```powershell
git diff --check
git status --short --branch
```

Commit only Task 03 changes and push the branch. Report branch, commit hash, tests run, route scope,
and deferred resume/cleanup/capability-validation notes.
