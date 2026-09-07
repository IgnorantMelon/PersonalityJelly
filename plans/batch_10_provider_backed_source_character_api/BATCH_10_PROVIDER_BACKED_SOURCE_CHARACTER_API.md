# Batch 10 Provider-Ready Source And Character API

Batch 10 is the implementation batch after Batch 09 Provider-Backed API Planning. Its purpose is
to implement the first provider-ready HTTP write workflow sequence without jumping into staged
provider-backed persona setup before the application service boundary is ready.

Follow `VIBE_CODING_GUIDE.md`, the Batch 08 closeout, and the accepted Batch 09 contracts:

- `plans/batch_09_provider_backed_api_planning/01_source_ingest_api_contract.md`
- `plans/batch_09_provider_backed_api_planning/02_character_persona_setup_api_contract.md`
- `plans/batch_09_provider_backed_api_planning/03_provider_backed_write_contract_matrix.md`

This batch may add application services, API schemas, routes, and tests for the selected route
scope. It must not implement provider-backed persona setup, turn execution, summary generation,
benchmark execution, auth/workspace features, UI, deployment, queues, cursor migration, or semantic
behavior changes.

Batch 10 development task prompts are development tasks only. Coordinator integration, route
audit, final regression runs, docs/status updates, and post-batch handoff notes are batch
acceptance work, not numbered task prompts inside this batch.

## Scope Decision

Batch 10 should implement:

1. `POST /source-works`
2. `POST /characters`

`POST /source-works` is first because Task 03 identifies it as the safest first implementation:
it creates the durable prerequisite for later character/persona setup, is deterministic, and
exercises Batch 08 workflow-run, workflow-link, audit, idempotency, replay, conflict, and redaction
foundations without introducing provider partial-persistence complexity.

`POST /characters` is included as a deterministic bridge because it is the next required resource
after source ingest and can share the same local write foundations. It must remain a separate route
from source ingest and from persona setup.

`POST /characters/{character_id}/persona-setup-runs` is deferred. Task 03 says this is the first
true provider-backed route only after staged application-service hardening exists: role-specific
provider bundles, request/workflow/step trace correlation, staged commits, provider failure
normalization, partial-persistence replay, and terminal idempotency storage. Implementing it in
Batch 10 would mix deterministic resource creation with unresolved staged provider semantics.

## Planning Branch

This Batch 10 plan is created by Batch 09 Task 04 on:

| Branch | Branch base | Purpose |
| --- | --- | --- |
| `planning/batch-10-provider-api-implementation` | `planning/api-provider-write-contract-matrix` at Task 03 commit `53b2becb70ed18079408ff36806f046bc18bb193` | Next implementation batch plan and prompts only. |

## Implementation Branches

Future implementation should start after Batch 09 planning is accepted by the coordinator and
merged or integrated onto the selected base. If the coordinator chooses dependency branches before
`dev` merge, preserve the order below and use the completed prerequisite branch as the next base.

| Task | Branch | Branch base | Depends on | Main output |
| --- | --- | --- | --- | --- |
| 01 Source Ingest Application Workflow | `feature/api-source-ingest-application-workflow` | accepted Batch 09/10 planning base, normally clean `dev` after Batch 09 closeout | Batch 08 foundations and Batch 09 source ingest contract | `personality_jelly.application.sources` service, workflow/audit/link/idempotency-ready result models, focused application tests. |
| 02 Source Ingest API Route | `feature/api-source-ingest-route` | completed Task 01 branch | 01 | `POST /source-works` schemas, thin route, redaction, idempotency replay/conflict, route/OpenAPI tests. |
| 03 Character Creation Workflow And Route | `feature/api-character-create-route` | completed Task 02 branch | 01, 02 | `create_character_workflow`, `POST /characters`, deterministic bridge tests using source ingest prerequisites. |

Recommended integration branch:

- `integration/batch-10-source-character-api`

The coordinator should create the integration branch from clean `dev`, merge accepted Tasks 01, 02,
and 03 in order, then run the batch-level acceptance checks listed below before final `dev`
integration. Sequential dependency branches are preferred for implementation work, so no
intermediate integration branch is required before Task 03 unless conflicts appear.

## Expected Route Scope

Add exactly these write routes:

- `POST /source-works`
- `POST /characters`

Keep existing read-only routes unchanged except for OpenAPI updates caused by the new routes. The
existing diagnostic routes must be able to inspect created audit and workflow records:

- `GET /workflow-runs/{workflow_id}`
- `GET /workflow-runs?request_id=...`
- `GET /workflow-runs?workflow_type=source_work.ingest`
- `GET /workflow-runs?workflow_type=character.create`
- `GET /audit-events/{audit_event_id}`
- `GET /audit-events?workflow_id=...`

Do not add these deferred routes in Batch 10:

- `POST /characters/{character_id}/persona-setup-runs`
- `POST /character-persona-setup-runs`
- `POST /source-ingestions`
- multipart upload or remote URL ingest routes
- provider-backed embedding/source enrichment routes
- turn, summary, benchmark, auth, workspace, platform, UI, deployment, queue, or cursor routes

## Application-Service Gaps

Task 01 must add an HTTP-safe source ingest application service. Suggested module:

- `personality_jelly.application.sources`

Expected service boundary:

- Accept inline text only, represented as a `LoadedSource` with `path=None`.
- Reject local path fields and path-like nested metadata before workflow start.
- Validate `title`, `source_type`, `content`, `content_encoding`, and chunking options before
  durable writes.
- Enforce an explicit source content size limit and chunking bounds chosen in implementation.
- Reject zero-chunk output before workflow, audit, domain, or idempotency rows are persisted.
- Use `personality_jelly.ingestion.ingest_loaded_source`; do not use `ingest_text_file` for HTTP.
- Persist one `SourceWork`, all `SourceChunk` rows, one audit event, one workflow run, workflow
  links, and the idempotency replay record under one success boundary.
- Return a transport-neutral result with source metadata, chunk count, chunk IDs,
  `text_redacted=true`, `source_preview_redacted=true`, and `llm_trace_ids=[]`.

Task 03 must add or harden deterministic character creation as an application workflow. Suggested
module:

- `personality_jelly.application.characters` or `personality_jelly.application.character_creation`

Expected service boundary:

- Wrap `personality_jelly.characters.create_character`.
- Validate source work existence, canonical name, aliases, optional explicit `character_id`, actor,
  and request correlation.
- Map duplicate name and explicit ID collision to `ConflictError`.
- Persist character, workflow run/links, audit event, and optional idempotency replay in one
  success boundary.
- Return compact character identity with `latest_persona_version_id=null`.

API handlers must remain thin adapters. They may validate Pydantic request/response models, resolve
headers, load/store idempotency replay, call application services, map errors, and apply redaction.
They must not call ingestion, character repositories, extraction, persona, provider, or semantic
modules directly.

## Storage And Migration Expectations

No schema migration is required for the minimal Batch 10 scope.

Use existing storage:

- `source_works`
- `source_chunks`
- `characters`
- `audit_events`
- `workflow_runs`
- `workflow_run_links`
- `idempotency_records`

Do not add source content hashes, upload tables, provider-run tables, persona setup attempt tables,
or new provider trace fields in Batch 10. Route-specific many-ID lists should live in
`result.persisted_ids` and `workflow_run_links`; do not expand `WorkflowRelatedIds` unless a focused
implementation proves it is simpler and remains fully tested.

If a task unexpectedly needs a schema migration, stop and update the task plan before implementing
it. Migration changes must include storage migration/schema tests and coordinator review because
Batch 10 is designed to avoid migrations.

## Audit, Workflow, Idempotency, Failure, And Redaction

`POST /source-works` requirements:

- workflow type: `source_work.ingest`
- audit operation: `source_work.ingest`
- status on success: `201 Created`
- `Idempotency-Key` required; optional body `idempotency_key` must match the header
- same idempotency key and same request hash replays the stored redacted `201` payload
- same idempotency key and different request hash returns `409 conflict`
- explicit `source_work_id` collision returns `409 conflict`
- validation failures persist nothing
- deterministic storage failures roll back source work, chunks, audit event, workflow completion,
  links, and idempotency replay together
- provider failure and partial persistence are not valid outcomes
- `llm_trace_ids` is always an empty list

`POST /characters` requirements:

- workflow type: `character.create`
- audit operation: `character.create`
- status on success: `201 Created`
- `Idempotency-Key` optional, but if supplied it must use the same header/body match, replay, and
  conflict helpers as existing deterministic write routes
- missing source work returns `404 not_found`
- duplicate canonical name in one source work and explicit `character_id` collision return
  `409 conflict`
- validation failures persist nothing
- provider failure and partial persistence are not valid outcomes

Common redaction rules:

- Never return or persist raw source `content`, source chunk text, source previews, local paths,
  path-like metadata values, raw request bodies, SQL, stack traces, provider config, prompts,
  secrets, or auth headers in write responses, audit metadata, workflow metadata, idempotency
  replay payloads, or error details.
- Default responses may include IDs, counts, source metadata, character identity, timestamps,
  workflow status, audit IDs, workflow IDs, and redaction booleans.
- Rejected path-like inputs should fail validation before workflow start when practical, and
  sanitizers must still scrub nested diagnostics defensively.

## Focused Tests

Task 01 application tests should live in a new focused file such as:

- `tests/test_application_source_ingest_workflow.py`

Task 02 API route tests should live in a new focused file such as:

- `tests/test_api_source_ingest_route.py`

Task 03 application/API tests should live in focused files such as:

- `tests/test_application_character_creation_workflow.py`
- `tests/test_api_character_creation_route.py`

OpenAPI contract tests may update:

- `tests/test_api_contract.py`

Batch-level regression tests to run after accepted development tasks are integrated:

- `tests/test_storage_migrations.py`
- `tests/test_storage_schema.py`
- `tests/test_repositories.py`
- `tests/test_application_correlation.py`
- `tests/test_application_idempotency.py`
- `tests/test_application_audit_workflow_inspection.py`
- `tests/test_api_correlation_error_envelope.py`
- `tests/test_api_audit_workflow_inspection.py`
- `tests/test_api_contract.py`

Full pytest is required before accepting Batch 10 because the batch adds new API write routes and
application services over shared audit/workflow/idempotency helpers.

## Batch Acceptance Requirements

The coordinator must verify these after the development task branches are integrated. These are
batch acceptance criteria, not standalone Batch 10 task prompts:

- route audit confirms Batch 10 added only `POST /source-works` and `POST /characters`;
- route handlers are thin adapters over `personality_jelly.application`;
- source ingest rejects path/file/url payloads and never echoes raw content;
- source ingest replay does not duplicate source work, chunks, audit events, workflow runs, links,
  or idempotency records;
- character creation can use a source created through `POST /source-works`;
- character creation replay/conflict behavior is covered when an idempotency key is supplied;
- workflow links exist for created source work, source chunks, character, audit event, and
  idempotency record where applicable;
- audit/workflow inspection routes expose safe diagnostics and no raw source text;
- OpenAPI schemas do not expose local path fields, provider config, raw prompts, raw outputs, or
  debug-only payloads;
- focused tests pass;
- full pytest passes;
- `README.md`, `VIBE_CODING_GUIDE.md`, and any post-batch status artifact accurately describe
  implemented and deferred scope.

## Deferred Batch 11 Handoff

After Batch 10 acceptance, the recommended next batch is provider-backed persona setup only:

- `POST /characters/{character_id}/persona-setup-runs`

That later batch should start from the accepted Batch 10 source/character API state and first harden
`run_character_persona_setup_workflow` or equivalent staged application service. It should not be
mixed with source ingest or deterministic character creation work.

Batch 11 prerequisites from Task 03 remain:

- setup-specific provider/model role bundle models for Reader, Verifier, and persona compiler;
- trace recorder plumbing for `request_id`, `workflow_id`, `workflow_step`, and related IDs;
- staged commit policy for Reader, Verifier, and persona compiler steps;
- provider transport, provider validation, no-candidate, no-verified, and terminal commit failure
  normalization;
- partial-persistence error/replay payload storage for success, failed, and partial outcomes;
- redacted setup success and partial/error response models;
- tests proving replay never recalls providers or duplicates setup rows.

## Non-Goals

- No provider-backed persona setup implementation.
- No combined source/character/persona convenience route.
- No source file path, server-local file reference, remote URL, multipart upload, binary/base64
  upload, source enrichment, or embeddings route.
- No provider config, API keys, raw prompts, prompt controls, semantic options, or model routing in
  the new Batch 10 request bodies.
- No turn execution, summary generation, OOC benchmark execution, retrieval benchmark execution,
  memory guard, critic, or follow-up workflow route.
- No auth, workspace, platform roles, billing, rate limits, CORS, deployment, queues, UI, external
  observability, graph/vector databases, LangGraph, or third-party memory systems.
- No changes to CLI `ingest_text_file` behavior.
- No semantic judgment changes, prompt edits, retrieval behavior changes, benchmark pass/fail
  changes, or memory guard rule changes.
- No cursor pagination migration.
