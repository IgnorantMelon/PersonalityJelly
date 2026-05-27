# Task 01 Prompt: Source Ingest Application Workflow

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_10_provider_backed_source_character_api/BATCH_10_PROVIDER_BACKED_SOURCE_CHARACTER_API.md`.

## Branch

Create the implementation branch from the accepted Batch 09/10 planning base, normally clean `dev`
after Batch 09 closeout:

```powershell
git switch dev
git pull --ff-only
git switch -c feature/api-source-ingest-application-workflow
```

If the coordinator provides a dependency integration branch instead of `dev`, use that branch as
the base and report the actual base in your final status.

## Read First

- `VIBE_CODING_GUIDE.md`
- `plans/batch_10_provider_backed_source_character_api/BATCH_10_PROVIDER_BACKED_SOURCE_CHARACTER_API.md`
- `plans/batch_09_provider_backed_api_planning/01_source_ingest_api_contract.md`
- `plans/batch_09_provider_backed_api_planning/03_provider_backed_write_contract_matrix.md`
- `plans/batch_08_api_workflow_persistence/BATCH_08_CLOSEOUT.md`
- `src/personality_jelly/ingestion/service.py`
- `src/personality_jelly/ingestion/chunker.py`
- `src/personality_jelly/application/conversations.py`
- `src/personality_jelly/application/memory_mutations.py`
- `src/personality_jelly/application/audit.py`
- `src/personality_jelly/application/correlation.py`
- `src/personality_jelly/application/idempotency.py`

## Goal

Add a transport-neutral application service for inline HTTP-safe source ingest. This task must not
add an API route. It prepares the service boundary that Task 02 will expose through
`POST /source-works`.

## Expected Implementation

Add a new application module, suggested:

- `src/personality_jelly/application/sources.py`

Export the accepted public models/functions from `src/personality_jelly/application/__init__.py`.

Implement a workflow service with a shape similar to:

- `SOURCE_WORK_INGEST_WORKFLOW_TYPE = "source_work.ingest"`
- `SourceWorkIngestRequest`
- `SourceWorkIngestResult`
- `SourceWorkSummary`
- `ingest_source_work_workflow(session, request)`

The request should carry:

- optional explicit `source_work_id`;
- `title`;
- optional `author`;
- `language`, defaulting to `zh-CN`;
- `source_type`, accepted values `markdown` and `txt`;
- inline `content`;
- optional `content_encoding`, accepted only as omitted or `utf-8`;
- optional chunking settings mapped to `ChunkingConfig`;
- required `LocalActorContext`;
- required `CorrelationContext`;
- sanitized client `metadata`.

Implementation requirements:

- Use `personality_jelly.ingestion.ingest_loaded_source` with a `LoadedSource` whose `path` is
  `None`.
- Do not use `ingest_text_file`; HTTP source ingest must not read server-local paths.
- Validate request shape, source type, content encoding, content size, chunking bounds, actor, and
  metadata before workflow start.
- Reject blank title, blank content, unsupported source type, unsupported encoding, invalid
  chunking, missing actor, oversized content, zero-chunk output, local path fields, path-like
  metadata values, remote URLs, file references, multipart hints, binary/base64 payload hints, and
  provider config.
- Choose explicit implementation constants for inline content size and chunking bounds. Keep them
  local and tested; do not add a config system in this task.
- Check explicit `source_work_id` collisions and raise `ConflictError`.
- Start a persisted workflow only after pre-validation succeeds.
- Persist `SourceWork`, `SourceChunk` rows, one audit event, workflow completion, workflow links,
  and idempotency replay support under one success boundary. The service itself should be ready to
  receive an idempotency context or should return enough data for Task 02 to store replay in the
  same write session; do not require a separate commit.
- Link the source work, every source chunk, and the audit event. Use relation values from Task 03:
  `created` and `audit`.
- Return route-specific `source_chunk_ids` under the result model instead of expanding
  `WorkflowRelatedIds`, unless you intentionally make that expansion with tests.
- Return `llm_trace_ids=[]`.

Audit event requirements:

- operation: `source_work.ingest`
- entity type: `source_work`
- result: succeeded
- before: `None`
- after: source metadata, chunk count, first/last chunk IDs, and redaction markers only
- metadata: request/workflow IDs, source type, language, chunk count, and sanitized client labels
- no raw source content, chunk text, local paths, provider config, secrets, SQL, stack traces, or
  raw request bodies

## Transaction And Failure Rules

- Validation failures persist nothing.
- Chunking failures and zero-chunk output persist nothing.
- Explicit `source_work_id` collision persists nothing.
- If any domain, audit, workflow, link, or replay storage step fails before success, roll back all
  source ingest rows.
- Do not return or persist provider failure, provider validation, or partial persistence outcomes.
  This route is deterministic.

If the existing `get_write_session` dependency or idempotency helper makes atomic replay storage
awkward, keep the service transaction-safe and document the remaining route-layer boundary in the
Task 02 handoff. Do not create partial commits to work around it.

## Tests

Add focused application tests, suggested file:

```powershell
.\.venv\Scripts\python -m pytest tests/test_application_source_ingest_workflow.py
```

Cover at least:

- inline Markdown persists one source work and all chunks;
- inline TXT is accepted;
- blank title, blank content, unsupported source type, unsupported encoding, missing actor, invalid
  chunking, oversized content, and zero-chunk output are rejected before source/audit/workflow rows;
- explicit `source_work_id` collision raises `ConflictError`;
- local path fields and path-like metadata values are rejected and not persisted raw;
- audit event persists operation `source_work.ingest`, source metadata, chunk count, and no raw
  content;
- workflow run and links persist for source work, every chunk, and audit event;
- result includes source metadata, chunk count, chunk IDs, redaction booleans, and
  `llm_trace_ids=[]`;
- a forced storage failure rolls back domain, audit, workflow, links, and replay-ready output.

Also run relevant shared focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests/test_ingestion_service.py tests/test_application_correlation.py tests/test_application_idempotency.py tests/test_application_audit_workflow_inspection.py
```

## Non-Goals

- Do not add `POST /source-works` in this task.
- Do not add source file path, upload, URL fetch, binary/base64, or embedding support.
- Do not add provider calls, LLM traces, prompts, semantic behavior, retrieval indexing, or source
  enrichment.
- Do not change CLI `ingest_text_file` behavior.
- Do not implement character creation or persona setup.
- Do not add migrations unless you stop and update the plan first.

## Completion

Run:

```powershell
git diff --check
git status --short --branch
```

Commit only Task 01 changes and push the branch. Report branch, commit hash, tests run, and any
handoff notes for Task 02.
