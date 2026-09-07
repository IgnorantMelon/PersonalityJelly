# Trace Workflow Correlation

Batch 06 Task 05 is a planning/readiness artifact. It defines request, workflow, and trace
correlation for future API write routes. It does not add middleware, routes, migrations, models,
trace columns, workflow-run tables, or persistence changes.

## Current State

- Batch 05 API routes are read-only FastAPI adapters over `personality_jelly.application`.
- API errors already use an envelope with `code`, `message`, `details`, and optional `trace_id`,
  but the current handlers never populate a request or workflow correlation field.
- `application` services expose transport-neutral workflow wrappers for turn execution, summary,
  character persona setup, benchmarks, inspection, provider role bundles, and payload-only audit
  readiness.
- `storage/models.py` and `storage/migrations/` do not exist in the current tree. Durable domain
  shapes live in `domain/models.py`, ORM rows live in `storage/orm.py`, repositories live in
  `storage/repositories.py`, and migrations live in `storage/migrations.py`.
- `LLMRawOutput` persists structured JSON LLM call traces with `id`, `operation`, `schema_name`,
  `provider_name`, `model_name`, `raw_output`, `response_schema`, `parsed_output`,
  `validation_errors`, and `created_at`.
- Existing durable business links already cover much of the debug path:
  - `Conversation` links `user_id`, `character_id`, and `persona_version_id`.
  - `Message` links to `conversation_id`, and assistant messages link to `context_package_id`.
  - `ContextPackage` links to `conversation_id`, `persona_version_id`, claim IDs, memory IDs, and
    retrieved chunk IDs.
  - `CriticReport` links to assistant `message_id`.
  - `FailureCase` links `conversation_id`, user/assistant message IDs, `context_package_id`, and
    `critic_report_id`.
  - `EvaluationCaseResult` links an OOC benchmark run to assistant message and critic report IDs.
  - `RetrievalEvaluationCaseResult` links retrieval runs to expected and retrieved chunk IDs.
  - payload-only audit events can carry related IDs but are not persisted.
- Existing gaps are also clear:
  - no durable request ID;
  - no durable application workflow/run ID;
  - no first-class link from `LLMRawOutput` to conversations, messages, context packages, critic
    reports, memories, eval runs, failure cases, audit events, or workflow runs;
  - structured LLM trace callers usually ignore the returned `LLMRawOutput`, so workflow summaries
    cannot report trace IDs consistently;
  - roleplay `generate_text` calls and embedding calls are not recorded as `LLMRawOutput` rows;
  - retrieval benchmark runs do not produce LLM trace rows unless a future embedding trace model is
    added;
  - audit events are payload-only and cannot yet be queried by correlation ID.

## Correlation Concepts

### Request ID

`request_id` is a transport-level correlation ID for one HTTP request.

- It is generated or normalized at the API boundary.
- It should be accepted from an `X-Request-ID` header or a write body `request_id`. If both are
  present, they must match after normalization or the route returns `422 validation_error`.
- If the client omits it, the API boundary should generate one, for example `req_<uuidhex>`.
- It must be a nonblank bounded string. Recommended maximum: 128 characters.
- It is not a domain entity, not proof of identity, and not an auth or permission subject.
- It may become part of idempotency later, but request correlation alone is not enough to replay
  provider-backed workflows safely.

### Workflow ID

`workflow_id` is an application-level ID for one application workflow invocation.

- It is generated or adopted by the application service, not by domain modules.
- It should use an explicit prefix such as `wf_<uuidhex>` if a new `EntityKind` is added later.
- One request can create one workflow in the first write implementation. Later async or batch
  endpoints may create multiple child workflow IDs under the same request ID.
- Provider-backed routes should require or return a workflow ID before they claim retry safety.
- A workflow ID is the recommended durable correlation key for messages, context packages, traces,
  failure cases, memories, eval runs, and audit events created during one business operation.

### Run IDs

Some domain workflows already have durable run IDs:

- OOC benchmark root: `EvaluationRun.id`.
- Retrieval benchmark root: `RetrievalEvaluationRun.id`.

These remain domain run IDs. Do not rename them to workflow IDs. Future benchmark write responses
should return both:

- `workflow_id` for API/application correlation and idempotency;
- `evaluation_run_id` or `retrieval_evaluation_run_id` for domain inspection.

### LLM Trace ID

`llm_trace_id` is `LLMRawOutput.id`.

- It identifies one persisted structured JSON LLM operation.
- It must not be overloaded as `request_id` or `workflow_id`.
- Future workflow responses may include `llm_trace_ids` as a list because one workflow can call
  mode classifier, critic, memory curator, memory guard, summary, reader, verifier, persona
  compiler, and benchmark evaluator steps.
- When a provider validation failure creates a trace row, error responses should expose the safe
  trace ID while still applying redaction policy to raw trace payloads.

### Domain Object IDs

Future write responses and audit payloads should preserve these IDs whenever known:

- `source_work_id`;
- `character_id`;
- `user_id`;
- `conversation_id`;
- `persona_version_id`;
- `user_message_id`;
- `assistant_message_id`;
- `rejected_assistant_message_id`;
- `context_package_id`;
- `critic_report_id`;
- `rejected_critic_report_id`;
- `failure_case_ids`;
- `memory_ids`;
- `evaluation_run_id`;
- `evaluation_case_result_ids`;
- `retrieval_evaluation_run_id`;
- `retrieval_evaluation_case_result_ids`;
- `audit_event_id` or `audit_event_ids` once persistent audit exists.

## Generation Boundaries

### Generated Per HTTP Request

The API boundary should generate or normalize:

- `request_id`;
- a request start timestamp for logging and later latency metadata;
- a transport-safe correlation object passed into the application service;
- response/error envelope correlation fields.

The API boundary should not generate domain entity IDs, LLM trace IDs, or semantic workflow state.
It should not import domain workflow internals to infer related IDs.

### Generated Per Application Workflow

The application service should generate or adopt:

- `workflow_id`;
- `workflow_type`, such as `conversation.create`, `conversation.turn`,
  `conversation.summarize`, `memory.review`, `benchmark.ooc.run`, or
  `benchmark.retrieval.run`;
- workflow status: `accepted`, `running`, `completed`, `failed`, or `partial`;
- workflow step names for provider-backed steps, such as `mode_classification`,
  `context_build`, `roleplay_generate`, `critic_evaluate`, `memory_curate`,
  `memory_guard`, `summary_generate`, `benchmark_case_evaluate`, `reader_extract`,
  `verifier_verify`, and `persona_compile`;
- related IDs as each durable object is created or loaded.

The application service should not depend on FastAPI request objects, headers, route classes, or
HTTP exceptions. It should accept a transport-neutral correlation input model.

### Generated Per Durable Record

Existing repositories should keep generating current entity IDs through `generate_id` unless a
future route explicitly accepts a client-supplied ID with collision/idempotency rules. Generated
domain IDs are not substitutes for workflow IDs.

LLM trace IDs should continue to be generated by `RepositoryLLMTraceRecorder` when a trace row is
persisted.

## Application-Service Flow

Add transport-neutral correlation models before implementing write routes:

```python
class CorrelationContext(InspectionModel):
    request_id: str
    workflow_id: str | None = None
    workflow_type: str | None = None
    actor_id: str | None = None


class WorkflowContext(InspectionModel):
    request_id: str
    workflow_id: str
    workflow_type: str
    actor_id: str | None = None
```

The exact module can be `personality_jelly.application.correlation` or an equivalent application
boundary module. It must not live in `personality_jelly.api`.

Recommended flow:

1. API write handler validates request body, header correlation, and actor context.
2. API handler creates `CorrelationContext(request_id=...)`.
3. API handler calls one application service and passes the correlation context.
4. Application service creates or validates `workflow_id`, converts the input to `WorkflowContext`,
   and owns workflow step naming.
5. Application service passes only the minimal workflow context to lower orchestration helpers.
6. Trace recorder factory attaches workflow context to future trace rows or workflow-link records.
7. Application result models return workflow IDs, domain IDs, trace IDs, warning details, and
   optional payload-only audit events.
8. API handler serializes the result without adding workflow semantics.

Domain modules such as `runtime`, `memory`, `critic`, `evaluation`, `extraction`, and `persona`
should remain usable from CLI paths. If they accept correlation later, the parameter should be
optional and typed to an application/domain-neutral context or trace recorder, never to FastAPI.

## Existing Trace Linkage

Current structured traces cover:

- `runtime.mode.classify_interaction_mode`;
- `critic.evaluate_message`;
- `memory.curator.extract_candidates`;
- `memory.guard.semantic_decision`;
- `runtime.summary.conversation_summary`;
- `evaluation.benchmark.case_evaluation`;
- reader extraction, verifier, and persona compilation paths used by character persona setup.

Existing persisted links outside trace rows already make many workflows navigable:

- turn response summary returns conversation, user message, assistant message, context package,
  critic report, rejected message/report, failure case, and memory IDs;
- failure cases link rejected or logged assistant outputs back to messages, context, and critic
  reports;
- OOC case results link to assistant message and critic report, and the assistant message links to
  the context package;
- retrieval case results store expected/retrieved chunk IDs and scores.

These links are enough for read-only inspection but not enough for request-level debugging because
they require operation/time inference to connect LLM trace rows.

## Schema Gaps

Before provider-backed write routes are accepted, resolve these schema/service gaps:

1. `llm_raw_outputs` has no `request_id`, `workflow_id`, `workflow_step`, or related entity IDs.
2. `messages`, `context_packages`, `critic_reports`, `failure_cases`, `memories`, eval runs, and
   eval case results have no workflow correlation fields.
3. There is no `workflow_runs` table to record started, completed, failed, or partial workflow
   outcomes.
4. There is no `workflow_run_links` table to associate one workflow with arbitrary domain rows.
5. There is no idempotency/replay table keyed by `request_id` or `workflow_id`.
6. There is no persistent audit table, so audit IDs cannot be searched after the response.
7. Existing trace callers do not consistently return the `LLMRawOutput.id` to workflow result
   models.
8. Roleplay text generation and embeddings have no equivalent persisted trace or provider-call
   record.

## Migration Options

### Option A: Response-Only Correlation

Add no schema. Generate `request_id` and `workflow_id` at runtime and return them in write
responses/errors.

Use only for deterministic early routes, such as conversation creation and manual memory mutation,
where durable object IDs and payload-only audit events are enough for local debugging.

This option is not sufficient for turn execution, summary generation, persona setup, or benchmarks
because a later failure cannot be searched by request/workflow ID after the response is gone.

### Option B: Add Nullable Columns To Existing Tables

Add `request_id`, `workflow_id`, and possibly `workflow_step` columns to high-value tables:

- `llm_raw_outputs`;
- `messages`;
- `context_packages`;
- `critic_reports`;
- `failure_cases`;
- `memories`;
- `evaluation_runs`;
- `evaluation_case_results`;
- `retrieval_evaluation_runs`;
- `retrieval_evaluation_case_results`;
- future `audit_events`.

This makes common queries simple but spreads correlation fields across many tables and still does
not record workflow status, failures before domain rows exist, or idempotent replay outcomes.

### Option C: Workflow Run And Link Tables

Add a first-class workflow root and generic links:

- `workflow_runs`
  - `id`;
  - `request_id`;
  - `workflow_type`;
  - `status`;
  - `actor_type`, `actor_id` when actor context exists;
  - optional primary IDs: `source_work_id`, `character_id`, `user_id`, `conversation_id`,
    `persona_version_id`;
  - `started_at`, `completed_at`;
  - `error_code`, `error_message`, `failed_step`;
  - compact `metadata` JSON for warnings, retry counts, and result counts.
- `workflow_run_links`
  - `id`;
  - `workflow_id`;
  - `entity_type`;
  - `entity_id`;
  - `relation`, such as `created`, `read`, `trace`, `failure`, `audit`, `result`, or `input`;
  - `created_at`.

Indexes should include:

- `workflow_runs(request_id)`;
- `workflow_runs(workflow_type, started_at)`;
- `workflow_runs(status, started_at)`;
- `workflow_run_links(workflow_id)`;
- `workflow_run_links(entity_type, entity_id)`.

This option handles failures before domain rows exist and avoids adding nullable columns to every
domain table, but it needs careful service code to create links whenever records are created.

### Option D: Hybrid

Use `workflow_runs` plus `workflow_run_links` as the durable source of workflow state, and add a
small number of direct nullable columns where query value is highest:

- `llm_raw_outputs.request_id`;
- `llm_raw_outputs.workflow_id`;
- `llm_raw_outputs.workflow_step`;
- optionally `llm_raw_outputs.related_ids` JSON for low-frequency secondary links.

This is the recommended migration path.

It keeps workflow status and idempotency centered in one table while making trace listing/filtering
fast enough for diagnostics. It also avoids forcing every existing domain row to carry correlation
columns before real API usage proves the need.

## Recommended Correlation Model

Use the hybrid model:

1. Implement response-only `request_id` and `workflow_id` for the first deterministic write routes.
2. Before exposing provider-backed write routes, add `workflow_runs` and `workflow_run_links`.
3. In the same or next focused migration, add direct correlation fields to `llm_raw_outputs`:
   `request_id`, `workflow_id`, `workflow_step`, and optional `related_ids` JSON.
4. Keep domain entity tables unchanged unless a specific route proves that direct filtering by
   workflow ID is needed.
5. Extend application workflow results to collect and return all created trace IDs and workflow
   links.

The workflow ID should be the primary durable correlation key for application debugging. The
request ID should remain the transport key that groups API logs and one or more workflow IDs.

## API Response Expectations

Future write responses should include a top-level correlation section or equivalent first-class
fields:

```json
{
  "request_id": "req_...",
  "workflow_id": "wf_...",
  "workflow_type": "conversation.turn",
  "status": "completed",
  "ids": {
    "conversation_id": "conv_...",
    "user_message_id": "msg_...",
    "assistant_message_id": "msg_...",
    "context_package_id": "ctx_...",
    "critic_report_id": "cr_...",
    "failure_case_ids": [],
    "memory_ids": [],
    "llm_trace_ids": []
  },
  "result": {},
  "warnings": []
}
```

Rules:

- `request_id` is always returned by write routes.
- `workflow_id` is always returned by write routes after the application service starts.
- `ids` must include every durable created or linked ID known at response time.
- `llm_trace_ids` should be a list, not a single field.
- `audit_event` or `audit_event_ids` should follow Task 02's payload-only and future persistence
  boundary.
- Sensitive fields remain governed by the Batch 06 redaction policy. Correlation IDs are safe to
  return, but raw prompts, raw outputs, full source chunks, and local paths are not made safe by
  being correlated.
- Read-only detail/list endpoints do not need to add correlation fields until they intentionally
  expose workflow-run inspection or workflow-filtered lists.

## Error Envelope Expectations

Do not overload `trace_id` with request or workflow IDs. It is ambiguous with `llm_trace_id`.

Recommended future error body:

```json
{
  "error": {
    "code": "provider_validation_error",
    "message": "Provider output failed schema validation",
    "details": {
      "failed_step": "critic_evaluate",
      "llm_trace_ids": ["llmraw_..."],
      "persisted_ids": {
        "conversation_id": "conv_...",
        "user_message_id": "msg_...",
        "context_package_id": "ctx_..."
      },
      "retry_hint": "retry_with_same_workflow_id_after_idempotency_support"
    },
    "trace_id": "llmraw_...",
    "request_id": "req_...",
    "workflow_id": "wf_..."
  }
}
```

Compatibility path:

- Keep the current `trace_id` field for now.
- Add `request_id` and `workflow_id` as explicit optional fields in the error body when the API
  schema is intentionally migrated.
- Until that migration, place `request_id` and `workflow_id` under `details.correlation` and keep
  `trace_id` for a single relevant `llm_trace_id` only.

Error rules:

- validation errors before the application service starts should include `request_id` but may have
  `workflow_id=null`.
- application validation, lookup, conflict, and actor errors should include both IDs when a
  workflow has started.
- provider validation failures should include safe `llm_trace_ids` if trace rows were persisted.
- partial-persistence errors should include `persisted_ids`, `failed_step`, `llm_trace_ids`, and a
  retry hint.
- unexpected errors must not leak raw prompts, raw provider payloads, secrets, local paths, or stack
  traces in details.

## Required Service Changes

Before implementing write routes:

1. Add application-level correlation input/result models.
2. Add a write-route request dependency/helper that normalizes `X-Request-ID` and body
   `request_id`.
3. Add workflow result fields to future write response models: `request_id`, `workflow_id`,
   `workflow_type`, `status`, `ids`, `warnings`, and `partial`.
4. Update future application write services to accept correlation context and return workflow
   summaries without importing API modules.
5. Add a trace recorder factory or context-aware recorder so workflow services can attach
   `workflow_id`, `request_id`, and `workflow_step` to future `LLMRawOutput` rows or workflow links.
6. Update structured LLM call sites to retain returned trace IDs where the workflow result needs
   them.
7. Add normalized write error classes or normalized error metadata for `conflict`,
   `provider_failure`, `provider_validation_error`, `partial_persistence`, `critic_failure`, and
   `guard_failure`.
8. Add audit metadata propagation for `request_id` and `workflow_id` after Task 02's actor/audit
   contract is implemented.
9. Keep CLI callers working by making correlation optional or by creating CLI workflow contexts
   inside application services when needed.

## Required Schema Changes

Recommended before provider-backed HTTP write routes:

1. Add `workflow_runs`.
2. Add `workflow_run_links`.
3. Add `request_id`, `workflow_id`, `workflow_step`, and optional `related_ids` JSON to
   `llm_raw_outputs`.
4. Add indexes for request/workflow trace queries.
5. Add a future `audit_events.workflow_id` or workflow link relation when persistent audit is
   implemented.

Not required for the first deterministic write implementation:

- adding workflow columns to every domain table;
- tracing roleplay `generate_text`;
- tracing embeddings;
- creating external observability exports.

## Workflow-Specific Expectations

### Conversation Creation

- Request boundary: `request_id`.
- Workflow boundary: `workflow_id` with `workflow_type=conversation.create`.
- Response IDs: `conversation_id`, `user_id`, `character_id`, `persona_version_id`.
- Can use response-only correlation in the first deterministic implementation.

### Manual Memory Review/Edit/Archive

- Request boundary: `request_id` plus local actor context.
- Workflow boundary: `workflow_id` with `workflow_type=memory.review`, `memory.edit`, or
  `memory.archive`.
- Response IDs: `memory_id`, owner IDs, optional `conversation_id`, and payload-only audit event
  ID.
- Future persistent audit should link the audit event to the workflow.

### Turn Execution

- Requires durable workflow correlation before HTTP exposure.
- Response IDs: conversation, user message, assistant message, context package, critic report,
  rejected assistant/report IDs, failure case IDs, memory IDs, and all LLM trace IDs available.
- Partial errors must state whether user message, context package, assistant message, critic report,
  failure cases, or memories were persisted.
- Roleplay `generate_text` has no trace row today; the assistant message ID is the durable output
  reference until text-generation trace persistence is planned.

### Summary Generation

- Requires workflow correlation before HTTP exposure if provider failure traces are expected to be
  debugged after response time.
- Response IDs: `conversation_id`, summary `llm_trace_ids`, and optional message range metadata if
  future summary versioning is added.
- Validation failure should expose summary trace ID if the invalid provider output was recorded.

### Character Persona Setup

- Requires durable workflow correlation and staged links before HTTP exposure.
- Response IDs: `source_work_id`, `character_id`, candidate claim IDs, evidence ref IDs, verified
  claim IDs, conflict IDs, `persona_version_id`, and reader/verifier/compiler trace IDs.
- Workflow steps should separate reader extraction, verifier validation, and persona compilation.

### OOC Benchmark Execution

- Requires durable workflow correlation and staged run status before HTTP exposure.
- Response IDs: `evaluation_run_id`, case result IDs, assistant/context/critic IDs when available,
  and benchmark evaluator trace IDs.
- `evaluation_run_id` remains the domain run root; `workflow_id` remains API/application
  correlation.

### Retrieval Benchmark Execution

- Requires durable workflow correlation and staged run status before HTTP exposure.
- Response IDs: `retrieval_evaluation_run_id`, retrieval case result IDs, expected/retrieved chunk
  IDs.
- There are no LLM trace IDs for embedding calls today. Do not invent fake `llm_trace_id` values.

## Future Tests To Add

Add these tests in the implementation batch that introduces correlation:

- API request normalization:
  - server generates `request_id` when absent;
  - header and body `request_id` must match when both are present;
  - blank or oversized request IDs return `422 validation_error`.
- Application boundary:
  - write services receive `CorrelationContext` and return `workflow_id` without importing FastAPI;
  - CLI/application callers still work when no HTTP request exists.
- Response contract:
  - successful write responses include `request_id`, `workflow_id`, `workflow_type`, `status`, and
    all created/linked IDs.
- Error contract:
  - validation before workflow start includes request ID and no workflow ID;
  - provider validation failure includes request ID, workflow ID, failed step, and safe trace ID;
  - partial persistence includes persisted IDs and retry hint.
- Trace persistence:
  - context-aware recorder stores request/workflow/step fields on `LLMRawOutput`;
  - LLM trace list/detail can filter or display workflow correlation without leaking raw payloads.
- Workflow links:
  - one turn workflow links user message, assistant message, context package, critic report,
    failure cases, memories, and trace IDs under the same workflow ID.
- Audit integration:
  - memory review/edit/archive audit payloads carry request/workflow metadata;
  - persistent audit, once added, links audit event ID to workflow ID.
- Idempotency readiness:
  - duplicate request/workflow IDs either replay a stored terminal outcome or return conflict,
    depending on the accepted idempotency design.

## Explicit Non-Goals

- No Batch 06 source code, tests, schema, migration, middleware, route, trace-persistence, README,
  or VIBE changes for this task.
- No write routes.
- No auth, CORS, UI, deployment, external observability, tracing SaaS, provider routing, graph
  database, vector database, or third-party memory system.
- No semantic behavior changes, prompt changes, benchmark pass/fail changes, retrieval changes, or
  keyword/regex/fixed-vocabulary judgment logic.
- No durable audit table in this task.

## Open Questions Blocking Provider-Backed Writes

- Should `workflow_id` be client-supplied for idempotency, server-generated with a separate
  idempotency key, or both?
- Should write responses use top-level `request_id` and `workflow_id`, a nested `correlation`
  object, or both during a compatibility window?
- Should roleplay `generate_text` calls get a separate provider-call trace table rather than being
  forced into `LLMRawOutput`, which is currently structured-output oriented?
- Should embedding calls use the same correlation mechanism as LLM calls or a separate retrieval
  diagnostic table?
- Is response-only correlation acceptable for conversation creation and manual memory mutation
  before `workflow_runs` exists, or should the first write implementation start by adding workflow
  persistence?
