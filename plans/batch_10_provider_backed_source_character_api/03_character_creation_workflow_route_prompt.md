# Task 03 Prompt: Character Creation Workflow And Route

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_10_provider_backed_source_character_api/BATCH_10_PROVIDER_BACKED_SOURCE_CHARACTER_API.md`.

## Branch

Start from the completed Task 02 branch:

```powershell
git switch feature/api-source-ingest-route
git pull --ff-only
git switch -c feature/api-character-create-route
```

If the coordinator provides a merged or integration base, use that base and report it.

## Read First

- `plans/batch_10_provider_backed_source_character_api/BATCH_10_PROVIDER_BACKED_SOURCE_CHARACTER_API.md`
- `plans/batch_09_provider_backed_api_planning/02_character_persona_setup_api_contract.md`
- `plans/batch_09_provider_backed_api_planning/03_provider_backed_write_contract_matrix.md`
- Task 01 and Task 02 implementations and tests
- `src/personality_jelly/characters/service.py`
- `src/personality_jelly/application/conversations.py`
- `src/personality_jelly/application/memory_mutations.py`
- `src/personality_jelly/api/routes/characters.py`
- `src/personality_jelly/api/schemas.py`

## Goal

Implement deterministic character creation as the bridge after source ingest:

- `POST /characters`

This route creates a character under an existing source work. It must not run Reader extraction,
Verifier validation, persona compilation, provider calls, or persona setup.

## Expected Application Implementation

Add or harden a transport-neutral application workflow. Suggested module:

- `src/personality_jelly/application/characters.py`
- or `src/personality_jelly/application/character_creation.py`

Export public models/functions from `src/personality_jelly/application/__init__.py`.

Expected public boundary:

- `CHARACTER_CREATE_WORKFLOW_TYPE = "character.create"`
- `CharacterCreateRequest`
- `CharacterCreateResult`
- `create_character_workflow(session, request)`

Request fields:

- `source_work_id` required;
- `canonical_name` required;
- `aliases` optional;
- `character_id` optional explicit ID;
- `actor` required;
- `correlation` required;
- `metadata` optional sanitized labels.

Application requirements:

- Validate actor context before mutation.
- Require the source work to exist.
- Normalize canonical name and aliases consistently with `personality_jelly.characters.create_character`.
- Map blank canonical name to validation failure.
- Map missing source work to `LookupError` or the accepted not-found application error.
- Map duplicate canonical name within a source work and explicit ID collision to `ConflictError`.
- Start a persisted workflow after validation/preflight succeeds.
- Persist character, audit event, workflow completion, workflow links, and optional idempotency
  replay support under one success boundary.
- Link source work as `input`, character as `created`, audit event as `audit`, and idempotency
  record as `idempotency` when available.
- Return compact character identity:
  `character_id`, `source_work_id`, `canonical_name`, `aliases`,
  `latest_persona_version_id=null`.

Audit requirements:

- operation: `character.create`
- entity type: `character`
- result: succeeded
- before: `None`
- after: compact character identity only
- metadata: sanitized request/workflow IDs, source work ID, alias count, client labels, and
  redaction markers
- no raw source text, chunk text, local paths, provider config, prompt text, secrets, SQL, stack
  traces, or raw request bodies

## Expected API Implementation

Add request/response schemas in the existing API style and wire `POST /characters` into
`src/personality_jelly/api/routes/characters.py` or a focused route module.

Request requirements:

- Optional `X-Request-ID`; must match body `request_id` when both are supplied.
- Optional `Idempotency-Key`; body `idempotency_key` must match when both are supplied.
- Required fields: `source_work_id`, `canonical_name`, `actor`.
- Optional fields: `request_id`, `idempotency_key`, `aliases`, `character_id`, `metadata`.
- Reject path-like metadata, provider config, prompt controls, source text, file/path fields, and
  raw secret fields.

Response requirements:

- HTTP `201 Created` on new character.
- Replays return the stored status and stored redacted payload.
- Use the write envelope style.
- `workflow_type` is `character.create`.
- `ids.source_work_id`, `ids.character_id`, `ids.audit_event_id`, and `ids.audit_event_ids` are
  populated.
- `result.character.latest_persona_version_id` is `null`.
- `result.audit_event` is redacted.

Error mapping:

- `404 not_found`: missing source work.
- `409 conflict`: duplicate canonical name in source work, explicit `character_id` collision, or
  idempotency hash mismatch.
- `422 validation_error`: blank canonical name, invalid actor, request ID mismatch, idempotency
  header/body mismatch, forbidden metadata fields.
- `500 unexpected_error`: sanitized defects.
- Provider failure, provider validation, and partial persistence are not valid outcomes.

## Tests

Add focused application tests, suggested:

```powershell
.\.venv\Scripts\python -m pytest tests/test_application_character_creation_workflow.py
```

Cover at least:

- successful character creation persists character, workflow run/link, audit event, and compact
  result;
- source work link is `input`, character link is `created`, and audit link is `audit`;
- missing source work returns not found and persists nothing;
- blank canonical name persists nothing;
- duplicate canonical name in the same source work raises `ConflictError`;
- explicit `character_id` collision raises `ConflictError`;
- audit metadata contains source/character IDs and alias counts but no raw source text or path-like
  values;
- optional idempotency replay storage can be performed without duplicating rows.

Add focused API tests, suggested:

```powershell
.\.venv\Scripts\python -m pytest tests/test_api_character_creation_route.py
```

Cover at least:

- successful `POST /characters` after creating a source with `POST /source-works`;
- generated request ID when omitted;
- `X-Request-ID` mismatch returns `422 validation_error`;
- optional idempotency replay returns stored payload without duplicate character/audit/workflow
  rows;
- same idempotency key with different body returns `409 conflict`;
- duplicate name conflict returns `409 conflict`;
- missing source work returns `404 not_found`;
- path-like metadata is rejected and redacted;
- diagnostics routes inspect workflow/audit records without raw source text.

Run relevant shared tests:

```powershell
.\.venv\Scripts\python -m pytest tests/test_character_service.py tests/test_api_contract.py tests/test_api_audit_workflow_inspection.py
```

## Non-Goals

- Do not implement `POST /characters/{character_id}/persona-setup-runs`.
- Do not combine character creation with source ingest or persona setup.
- Do not run Reader extraction, Verifier validation, persona compilation, providers, prompts,
  embeddings, retrieval, memory guard, critic, benchmark, or summary workflows.
- Do not add migrations unless you stop and update the plan first.
- Do not add auth/workspace/platform, uploads, URL fetches, UI, deployment, queues, CORS, or cursor
  migration.

## Completion

Run:

```powershell
git diff --check
git status --short --branch
```

Commit only Task 03 changes and push the branch. Report branch, commit hash, tests run, route
scope, and deferred persona setup notes.
