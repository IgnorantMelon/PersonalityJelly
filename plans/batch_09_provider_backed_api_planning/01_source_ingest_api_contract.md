# Source Ingest API Contract

Batch 09 planning artifact for a future source ingest HTTP write workflow. This document defines
the contract only. It does not implement routes, source behavior, storage schema changes, or tests.

## Recommendation

Implement source ingest before character/persona setup.

Recommended route:

- `POST /source-works`

Route choice:

- Choose `POST /source-works`, not `POST /source-ingestions`, for the first implementation because
  the route synchronously creates the durable `SourceWork` resource that clients need for the next
  character/persona setup step.
- Do not introduce a separate `source_ingestion` domain resource for this deterministic route.
  Batch 08 `workflow_runs`, `workflow_run_links`, audit events, and idempotency records already
  provide the diagnostic run surface.
- Reserve `POST /source-ingestions` for a later design only if source ingest becomes asynchronous,
  accepts multipart/upload references, or stages provider-backed enrichment such as embeddings.

Recommended workflow type and audit operation:

- workflow type: `source_work.ingest`
- audit operation: `source_work.ingest`

This workflow is deterministic in the first implementation. It should not call LLM or embedding
providers, should not read server-local file paths, and should commit a `SourceWork`, its
`SourceChunk` rows, the workflow run/links, the audit event, and the idempotency replay outcome
under one write-session success boundary.

## Current Implementation Surface

Existing reusable pieces:

- `personality_jelly.ingestion.ingest_loaded_source(session, loaded_source, ...)` creates one
  `SourceWork` plus stable `SourceChunk` rows from loaded text.
- `personality_jelly.ingestion.ingest_text_file(...)` reads a local path and must remain CLI-only
  for HTTP purposes.
- `SourceWork` fields are `id`, `title`, `author`, `language`, `source_type`, and `created_at`.
- `SourceChunk` fields are `id`, `source_work_id`, `chapter_index`, `chapter_title`,
  `paragraph_index`, `text`, `char_start`, and `char_end`.
- `ChunkingConfig` has `max_paragraph_chars` and `min_paragraph_chars`.
- Batch 08 provides persistent `audit_events`, `workflow_runs`, `workflow_run_links`,
  `idempotency_records`, write request correlation, and redacted error helpers.

Application-service gaps for implementation:

- Add `personality_jelly.application.sources.ingest_source_work_workflow`.
- Add API request/response models for source ingest under the shared write envelope style.
- Add source-work inspection/result summaries if the response needs more than ID and chunk counts.
- Extend `WorkflowRelatedIds` with `source_chunk_ids` or document source chunk IDs only under the
  route-specific `result`; the workflow must still link every created chunk through
  `workflow_run_links`.
- Add `AuditOperation.SOURCE_WORK_INGEST` or use the accepted string value until enum expansion is
  intentionally coordinated.

## Route Contract

### `POST /source-works`

Purpose: create a source work and its source chunks from inline TXT/Markdown content.

Accepted source payload forms:

| Form | Accepted in first implementation | Contract |
| --- | --- | --- |
| Inline UTF-8 TXT content | Yes | `source_type=txt`, `content` contains the full text. |
| Inline UTF-8 Markdown content | Yes | `source_type=markdown`, `content` contains the full text. |
| Server-local file path/reference | No | Reject before workflow start. Never read the path and never echo it in errors, audit metadata, workflow metadata, idempotency records, or replay payloads. |
| Client file name or provenance label | Metadata only | May be a bounded non-sensitive label inside `metadata` if it is not path-like. It is not dereferenced and must not control loading. |
| Multipart upload, remote URL, binary/base64 blob | No | Deferred until a separate file/upload contract is accepted. |

Request headers:

| Header | Required | Notes |
| --- | --- | --- |
| `X-Request-ID` | No | If supplied, must match body `request_id` after normalization. If omitted, the API generates `req_...`. |
| `Idempotency-Key` | Yes | Required for source ingest to avoid duplicate source works on client retry. If supplied with body `idempotency_key`, both values must match. |

Request body:

| Field | Required | Contract |
| --- | --- | --- |
| `request_id` | No | Bounded nonblank string, same normalization as existing write routes. |
| `idempotency_key` | No | Body mirror of `Idempotency-Key`; must match the header if both are present. |
| `source_work_id` | No | Optional client-supplied ID. If omitted, the application generates `sw_...`. |
| `title` | Yes | Nonblank source title. |
| `author` | No | Optional source author. |
| `language` | No | Defaults to `zh-CN`. |
| `source_type` | Yes | Accepted values for first implementation: `markdown` or `txt`. |
| `content` | Yes | Inline source text. Blank text is invalid. |
| `content_encoding` | No | Must be omitted or `utf-8`; binary/base64 upload is deferred. |
| `chunking` | No | Optional object with `max_paragraph_chars` and `min_paragraph_chars`; defaults to `ChunkingConfig`. |
| `actor` | Yes | Local actor context, same shape as current write routes, with `actor_type`, `actor_id`, optional `actor_label`, `user_id`, `operation_reason`, and `metadata`. |
| `metadata` | No | Bounded client labels. Must not contain secrets, prompts, provider payloads, or local paths. |

Rejected input forms:

- `local_path`, `file_path`, `path`, `uri`, or any server-local filesystem reference.
- path-like values in `metadata` or `actor.metadata`, including absolute Windows paths, POSIX paths,
  database URLs, provider URLs with credentials, or config-file paths.
- remote URL fetches.
- multipart file upload.
- binary/base64 payloads.
- provider config, embedding config, or prompt overrides.

Rejected file/path fields are validation errors, not redaction-only events. The error response may
name the rejected field family, but it must not echo the supplied path, URL, file name with
directories, or raw source text.

Initial limits to set in implementation:

- enforce a maximum `content` size before chunking;
- enforce bounded `chunking.max_paragraph_chars` and `chunking.min_paragraph_chars`;
- reject content that produces zero chunks unless the implementation explicitly supports empty
  source works.

The exact byte/character limits should live in the implementation batch after reviewing current
CLI expectations and test fixture sizes.

## Response Contract

Status on success: `201 Created`.

Response model should follow the existing write envelope:

```json
{
  "request_id": "req_...",
  "workflow_id": "wf_...",
  "workflow_type": "source_work.ingest",
  "status": "completed",
  "ids": {
    "source_work_id": "sw_...",
    "source_chunk_ids": ["chunk_..."],
    "audit_event_id": "audit_...",
    "audit_event_ids": ["audit_..."],
    "llm_trace_ids": []
  },
  "result": {
    "source_work": {
      "id": "sw_...",
      "title": "Novel title",
      "author": "Author name",
      "language": "zh-CN",
      "source_type": "markdown",
      "created_at": "..."
    },
    "chunk_count": 12,
    "chunk_ids": ["chunk_..."],
    "first_chunk_id": "chunk_...",
    "last_chunk_id": "chunk_...",
    "text_redacted": true,
    "source_preview_redacted": true
  },
  "warnings": []
}
```

Default response rules:

- Do not echo full `content`.
- Do not return full chunk text.
- Do not return source previews by default in this write response.
- Return source metadata, counts, stable IDs, and redaction booleans.
- Include `llm_trace_ids=[]` because this first source ingest route does not call providers.

If the implementation cannot add `source_chunk_ids` to `WorkflowRelatedIds` in Batch 10, then:

- keep `ids.source_work_id`, `audit_event_id`, and `audit_event_ids`;
- place `chunk_ids` in `result`;
- link every chunk through `workflow_run_links` using relation `created`.

## Error Contract

Use the existing error envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "content must not be blank",
    "details": {
      "correlation": {
        "request_id": "req_...",
        "workflow_id": "wf_...",
        "workflow_type": "source_work.ingest",
        "status": "failed"
      }
    },
    "trace_id": null
  }
}
```

Status and code mapping:

| HTTP | Code | Use |
| --- | --- | --- |
| 201 | n/a | Source work, chunks, audit event, workflow links, and optional idempotency replay are persisted. |
| 400 | `validation_error` | Unsupported content encoding or malformed JSON body if not handled by FastAPI's 422 path. |
| 404 | `not_found` | Not expected in the first inline-only create route. Reserved for future source references. |
| 409 | `conflict` | Explicit `source_work_id` already exists, or an idempotency key was reused with a different request hash. |
| 413 | `validation_error` | Content exceeds accepted size limit. If the shared mapper cannot emit 413 yet, use 422 and record this as a follow-up. |
| 422 | `validation_error` | Blank title/content, unsupported `source_type`, invalid chunking values, zero chunks after chunking, missing actor, missing idempotency key, header/body ID mismatch, or forbidden file/path/reference fields. |
| 500 | `unexpected_error` | Storage defects after sanitization. Must not leak local paths, SQL, source text, or stack traces. |

Provider failure codes are not expected for the first source ingest implementation. Do not return
`provider_failure`, `provider_validation_error`, or `partial_persistence` unless a later route adds
provider-backed enrichment such as embeddings.

## Transaction Boundary

The implementation should parse and chunk before the durable write when possible:

1. Normalize request correlation and idempotency key.
2. Validate actor context and request payload.
3. Check idempotency replay by `workflow_type=source_work.ingest` and request hash excluding
   `request_id` and `idempotency_key`.
4. Parse/chunk inline content in memory.
5. Begin the write transaction.
6. Start persisted workflow run with `status=running`.
7. Insert `SourceWork`.
8. Insert all `SourceChunk` rows.
9. Build and persist audit event.
10. Complete workflow run and create workflow links for the source work, chunks, and audit event.
11. Store idempotency replay payload if an idempotency key was supplied.
12. Commit.

Atomicity policy:

- If request validation fails, persist nothing.
- If content is oversized, a forbidden file/path field is present, or chunking produces zero chunks,
  fail before creating workflow, audit, domain, or idempotency rows.
- If chunking fails before the transaction, persist nothing.
- If source work insert, chunk insert, audit persistence, workflow completion, or idempotency replay
  storage fails, roll back the whole transaction.
- Do not claim partial success for this deterministic route.
- Do not create a source work without chunks unless a later implementation explicitly accepts empty
  source works.
- Do not store an idempotency replay record for validation failures in the first implementation.

If current helper layering makes idempotency replay storage occur after an inner service commit,
Batch 10 must first adjust the source ingest workflow so the replay record and domain rows share one
outer write-session success boundary.

## Audit Contract

Persist one audit event in the same transaction as the source work and chunks.

Audit event fields:

- `operation`: `source_work.ingest`
- `actor`: local actor context, `actor_type=api_user` by default
- `entity`: `{ "entity_type": "source_work", "entity_id": source_work_id }`
- `related_ids.source_work_id`: created source work ID
- `reason`: actor `operation_reason` if provided, else `local API source ingest requested`
- `before`: `null`
- `after`: source metadata and chunk count only; no raw source content or chunk text
- `metadata`: sanitized actor metadata, request/workflow IDs, source type, language, chunk count,
  and redaction markers
- `persistence`: current persistent audit event behavior from Batch 08

Audit metadata must not include raw source text, chunk text, local paths, provider config, secrets,
or stack traces.

## Workflow Run And Links

Workflow run:

- `workflow_type`: `source_work.ingest`
- initial status: `running`
- terminal status: `completed` or `failed`
- `persisted_ids`: source work ID, chunk IDs if supported, audit event ID
- warnings: empty list for the first implementation unless non-fatal metadata sanitization is
  explicitly added later

Workflow links:

| Entity type | Relation | Cardinality |
| --- | --- | --- |
| `source_work` | `created` | 1 |
| `source_chunk` | `created` | 0..n |
| `audit_event` | `audit` | 1 |
| `idempotency_record` | `idempotency` | 0..1 |

Read-only inspection expectations:

- `GET /workflow-runs/{workflow_id}` should show the source work ID, chunk IDs through links, audit
  event ID, and `status=completed`.
- `GET /audit-events/{audit_event_id}` should expose sanitized metadata and no source text.
- No new read-only source-work detail route is required in this task unless Batch 10 chooses to add
  one for API usability.

## Idempotency Contract

`Idempotency-Key` is required for the first HTTP source ingest route.

Scope:

- `workflow_type=source_work.ingest`
- `idempotency_key` from header/body after normalization
- request hash from the body excluding `request_id` and `idempotency_key`

Replay behavior:

- Same key and same request hash returns the stored `201` replay payload.
- Replay does not create additional source works, chunks, workflow runs, audit events, or traces.
- Replay response body must match the originally redacted response body.

Conflict behavior:

- Same key and different request hash returns `409 conflict`.
- Explicit `source_work_id` collision returns `409 conflict` unless the request is an idempotent
  replay through the idempotency table.
- Duplicate title alone is not a conflict in the first implementation because existing storage only
  has `find_by_title` and no accepted title uniqueness rule.

Request hash should include:

- source metadata fields;
- full inline `content`;
- chunking configuration;
- actor fields and sanitized metadata that materially affect the audit event.

Request hash should exclude:

- `request_id`;
- `idempotency_key`;
- generated IDs and timestamps.

Persisted idempotency record shape:

- `workflow_type=source_work.ingest`
- normalized `idempotency_key`
- `request_hash` as a SHA-256 digest only; do not store the canonical request body
- original successful `request_id` and `workflow_id`
- terminal `status=completed`
- `response_status_code=201`
- `replay_payload` equal to the redacted success response envelope
- `related_ids` limited to source work, audit, workflow, and chunk IDs

The idempotency record, replay payload, and `409 conflict` details must not store or return raw
source content, chunk text, source previews, local paths, provider config, secrets, or the conflicting
request body. Conflict details may include `workflow_type`, `idempotency_record_id`, and
`conflict=request_hash_mismatch`.

## Redaction Contract

Never expose:

- raw `content`;
- full chunk text;
- local filesystem paths or path-like request fields;
- source text inside audit metadata, workflow metadata, idempotency error details, or unexpected
  errors;
- secrets, auth headers, provider config, raw provider payloads, SQL, or stack traces.

Default write response exposes:

- source work metadata;
- chunk count;
- chunk IDs;
- first/last chunk IDs;
- redaction booleans such as `text_redacted=true`.

Local debug is deferred for this route. If a future local debug profile exposes chunk text, it must
do so through a targeted read route, not by echoing ingest response content.

Diagnostic persistence redaction:

- Audit `after` and `metadata` store only source metadata, chunk counts, IDs, result status, and
  redaction markers.
- Workflow `persisted_ids`, links, warnings, and error details store IDs/status only, not text.
- Idempotency `request_hash` stores only a digest; `replay_payload` stores the redacted response
  body only.
- Error details for validation, conflict, and unexpected failures must run through the shared
  sanitizer and should prefer stable field names over caller-supplied values.
- Absolute paths and path-like values are rejected at validation when possible and scrubbed from any
  residual diagnostics with `[redacted:path]`.

## Provider Failure And Partial Persistence

The first implementation is deterministic:

- no LLM provider;
- no embedding provider;
- no provider config;
- no provider traces.

Therefore:

- `provider_failure` and `provider_validation_error` are not valid outcomes;
- `llm_trace_ids` is always an empty list;
- `partial_persistence` should not occur because all durable writes share one transaction.

Future source enrichment routes, such as embedding creation, must be separate workflows with their
own provider failure and partial-persistence contracts.

## Tests Required In The Implementation Batch

Focused application tests:

- `ingest_source_work_workflow` persists one source work and all chunks from inline Markdown.
- The workflow rejects blank title, blank content, unsupported `source_type`, missing actor, and
  invalid chunking.
- Explicit `source_work_id` collision raises `ConflictError`.
- Audit event persists with operation `source_work.ingest`, source metadata, chunk count, and no raw
  source content.
- Workflow run and links persist for the source work, every chunk, and the audit event.
- Zero-chunk content is rejected before workflow/audit/idempotency rows are written.
- Idempotency records store a request hash digest and redacted replay payload only; raw `content`,
  chunk text, local paths, and forbidden metadata values are absent.
- Domain rows, audit event, workflow run, and idempotency replay roll back together when a forced
  storage failure occurs before commit.

Focused API route tests:

- `POST /source-works` returns `201`, write envelope fields, source metadata, chunk IDs, and no raw
  source text.
- Header/body `X-Request-ID` mismatch returns `422 validation_error`.
- Missing or mismatched `Idempotency-Key` returns `422 validation_error`.
- Same idempotency key and same body replays without duplicate source work/chunk/audit/workflow
  rows.
- Same idempotency key and different body returns `409 conflict`.
- Local path fields are rejected and redacted in error output.
- Path-like values in `metadata` and `actor.metadata` return `422 validation_error` and are never
  persisted raw.
- Oversized content maps to the accepted status/code.
- Zero-chunk content returns `422 validation_error` and leaves source/audit/workflow/idempotency
  tables unchanged.
- `GET /workflow-runs/{workflow_id}` and `GET /audit-events/{audit_event_id}` can inspect the
  created diagnostic records without raw source text.

Storage/schema tests:

- Only needed if Batch 10 extends `WorkflowRelatedIds`, source metadata storage, or introduces a
  content hash. No schema change is required for the minimal inline ingest route if chunk IDs stay
  in workflow links/result fields.

Contract tests:

- OpenAPI for `POST /source-works` must not expose local path fields, provider config, raw prompts,
  or debug-only payloads.
- Default response schema must not contain `content`, `text`, `source_text`, or full chunk text.

## Non-Goals

- No route implementation in Batch 09.
- No provider calls, embeddings, source enrichment, retrieval indexing, or prompt changes.
- No server-local path ingest over HTTP.
- No file upload, multipart upload, URL fetch, queues, async job runner, CORS, deployment, UI, auth,
  workspace, billing, or platform features.
- No change to existing CLI `ingest_text_file` behavior.
- No cursor pagination migration.
- No semantic behavior changes.

## Deferred Decisions

- Exact maximum source content size and chunking bounds.
- Whether to persist a source content hash on `SourceWork` for duplicate detection outside
  idempotency.
- Whether to add `source_chunk_ids` to `WorkflowRelatedIds` or keep chunk IDs route-specific.
- Whether a future read route should expose source work details before character/persona setup.
- Whether multipart upload is needed after the local-first API contract proves useful.
- Whether to introduce `POST /source-ingestions` later for asynchronous uploads, file references, or
  staged enrichment instead of overloading `POST /source-works`.
- Whether source ingest should eventually support embeddings as a separate provider-backed route.
