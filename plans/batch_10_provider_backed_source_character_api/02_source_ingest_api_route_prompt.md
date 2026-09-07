# Task 02 Prompt: Source Ingest API Route

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_10_provider_backed_source_character_api/BATCH_10_PROVIDER_BACKED_SOURCE_CHARACTER_API.md`.

## Branch

Start from the completed Task 01 branch:

```powershell
git switch feature/api-source-ingest-application-workflow
git pull --ff-only
git switch -c feature/api-source-ingest-route
```

If the coordinator provides a merged or integration base, use that base and report it.

## Read First

- `plans/batch_10_provider_backed_source_character_api/BATCH_10_PROVIDER_BACKED_SOURCE_CHARACTER_API.md`
- `plans/batch_09_provider_backed_api_planning/01_source_ingest_api_contract.md`
- `plans/batch_09_provider_backed_api_planning/03_provider_backed_write_contract_matrix.md`
- Task 01 implementation and tests
- `src/personality_jelly/api/app.py`
- `src/personality_jelly/api/schemas.py`
- `src/personality_jelly/api/routes/conversations.py`
- `src/personality_jelly/api/routes/characters.py`
- `src/personality_jelly/api/errors.py`
- `src/personality_jelly/api/redaction.py`

## Goal

Expose Task 01 through a thin FastAPI adapter:

- `POST /source-works`

This task should add request/response schemas, route wiring, idempotency replay/conflict behavior,
redaction, error mapping, and route/OpenAPI tests. It must not implement character creation or
persona setup.

## Expected Implementation

Add source API schemas and route code in the existing API style. Suggested files:

- `src/personality_jelly/api/source_schemas.py`, or a focused addition to `api/schemas.py`
- `src/personality_jelly/api/routes/sources.py`

Register the new router from `src/personality_jelly/api/app.py`.

Request requirements:

- Header `Idempotency-Key` is required.
- Optional body `idempotency_key` must match the header.
- Optional `X-Request-ID` must match body `request_id` when both are supplied.
- Required body fields: `title`, `source_type`, `content`, `actor`.
- Accepted `source_type` values: `markdown`, `txt`.
- Optional body fields: `request_id`, `idempotency_key`, `source_work_id`, `author`, `language`,
  `content_encoding`, `chunking`, `metadata`.
- Reject local path fields such as `local_path`, `file_path`, `path`, `uri`, path-like metadata,
  URL fetches, multipart/upload hints, binary/base64 payload hints, provider config, prompt
  controls, and raw secret fields.

Response requirements:

- HTTP `201 Created` on new ingest.
- Replays return the stored `201` status and stored redacted payload.
- Use the existing write envelope style: `request_id`, `workflow_id`, `workflow_type`, `status`,
  `ids`, `result`, `warnings`.
- `workflow_type` is `source_work.ingest`.
- `ids.source_work_id` is populated.
- `ids.audit_event_id` and `ids.audit_event_ids` are populated.
- `ids.llm_trace_ids` is an empty list.
- `result.source_work` contains source metadata only.
- `result.persisted_ids.source_chunk_ids`, `result.chunk_count`, `result.first_chunk_id`, and
  `result.last_chunk_id` are present.
- `result.text_redacted=true` and `result.source_preview_redacted=true`.
- Do not return `content`, chunk text, source previews, local paths, raw request bodies, or debug
  payloads.

Idempotency requirements:

- Use `resolve_write_request_idempotency`, `build_idempotency_context`,
  `load_idempotency_replay`, and `store_idempotency_replay` unless Task 01 introduced a narrower
  helper.
- Request hash must exclude `request_id` and `idempotency_key`; it must include full inline
  `content`, source metadata, chunking settings, actor fields, and behavior-affecting metadata.
- Same key and same request hash replays without duplicate source work, chunks, workflow run,
  workflow links, audit event, or idempotency record.
- Same key and different request hash returns `409 conflict` with sanitized details.

Error mapping:

- `422 validation_error`: missing idempotency key, header/body mismatch, blank fields, unsupported
  type/encoding, invalid chunking, forbidden path/reference fields, oversized content if 413 is not
  implemented, zero chunks, missing actor.
- `409 conflict`: idempotency hash mismatch or explicit `source_work_id` collision.
- `413 validation_error`: oversized content only if you add a tested mapper; otherwise use `422`
  and report the 413 status choice in the task result.
- `500 unexpected_error`: sanitized defects.
- Do not return provider failure, provider validation, or partial persistence for this route.

## Tests

Add focused API tests, suggested file:

```powershell
.\.venv\Scripts\python -m pytest tests/test_api_source_ingest_route.py
```

Cover at least:

- successful `POST /source-works` returns `201`, write envelope fields, source metadata, chunk IDs,
  audit IDs, workflow ID, and no raw source text;
- generated request ID when omitted;
- `X-Request-ID` and body `request_id` mismatch returns `422 validation_error`;
- missing `Idempotency-Key` returns `422 validation_error`;
- header/body idempotency mismatch returns `422 validation_error`;
- same key and same body replays without duplicate source work/chunk/audit/workflow rows;
- same key and different body returns `409 conflict`;
- explicit `source_work_id` collision returns `409 conflict`;
- local path fields and path-like metadata are rejected and redacted in the response;
- oversized content uses the accepted status/code;
- zero-chunk content returns `422 validation_error` and leaves source/audit/workflow/idempotency
  tables unchanged;
- `GET /workflow-runs/{workflow_id}` and `GET /audit-events/{audit_event_id}` inspect the created
  diagnostics without raw source text.

Update contract tests, likely:

```powershell
.\.venv\Scripts\python -m pytest tests/test_api_contract.py tests/test_api_correlation_error_envelope.py tests/test_api_audit_workflow_inspection.py
```

OpenAPI assertions must prove the route does not expose local path fields, provider config, raw
prompts, raw outputs, or debug-only payloads.

## Non-Goals

- Do not implement `POST /characters`.
- Do not implement persona setup or any provider-backed route.
- Do not add read routes for source work details unless the coordinator explicitly expands scope.
- Do not add upload, URL, binary/base64, path ingest, embeddings, queues, auth/workspace, UI,
  deployment, CORS, or cursor migration.
- Do not change CLI ingestion behavior.

## Completion

Run:

```powershell
git diff --check
git status --short --branch
```

Commit only Task 02 changes and push the branch. Report branch, commit hash, tests run, route
scope, and any implementation notes relevant to Task 03.
