# Task 01: Write Workflow Boundary Design

Batch 06 is a planning/readiness batch. This document defines future HTTP write
workflow boundaries only; it does not implement routes, source changes, schema
changes, or tests.

## Current State

- The FastAPI adapter is read-only. `create_app` wires route modules for health,
  conversation/context, character/claim/memory/source chunk, and diagnostics.
- API request handling uses one database session dependency. Current read-only
  requests always roll back after yielding the session.
- API errors use one envelope with `code`, `message`, `details`, and optional
  `trace_id`. Batch 05 maps lookup errors, validation errors, value errors, and
  unexpected exceptions.
- Reusable application/runtime services already exist for:
  - character persona setup: `build_character_persona`;
  - conversation summaries: `summarize_conversation_workflow`;
  - turn execution: `run_turn_workflow`;
  - OOC and retrieval benchmark wrappers;
  - payload-only audit event construction for manual memory operations.
- Domain/runtime services already exist for:
  - TXT/Markdown file ingestion and chunk persistence;
  - character creation;
  - user and conversation creation;
  - roleplay turn generation, context building, critic review, retry capture,
    memory curation, memory guard, and layered summaries.
- Repositories flush writes but leave commit/rollback ownership to the caller.
- Audit persistence is not implemented. Current audit helpers deliberately
  produce `payload_only` events.

## Boundary Principles

- `personality_jelly.api` remains an HTTP adapter. It validates HTTP input,
  acquires dependencies, calls application services, and maps errors.
- Workflow logic belongs in `personality_jelly.application` or existing domain
  service modules.
- Every write contract must carry explicit IDs. Do not hide current MVP
  single-work or single-character assumptions in API routes.
- Provider-backed workflows must be designed as partially persistent workflows
  before they are exposed over HTTP. Do not claim all-or-nothing semantics when
  a workflow can create traces, messages, failure cases, or eval rows before a
  later provider step fails.
- Canon writes remain evidence-backed. User and relationship memory writes must
  never rewrite canon or persona.
- Semantic behavior is unchanged. API write routes must not add keyword,
  regex, fixed-vocabulary, or string-containment semantic decisions.

## Workflow Classification

### Safe First Implementation Candidates

These workflows can be first write-route candidates after small
application-service wrappers are added. They avoid provider calls, are bounded
to one transaction, and can return the same inspection models that the read-only
routes already expose.

| Workflow | Why It Is Safe First | Required Wrapper |
| --- | --- | --- |
| Conversation creation | Deterministic row creation with existing user, character, and persona lookups. | `application.create_conversation_workflow` wrapping `runtime.create_conversation` and returning `ConversationDetail` or a strict summary. |
| Manual memory review | Existing repository enforces candidate-only review and accepted/rejected targets. | `application.review_memory_workflow` that returns `MemorySummary` plus payload-only audit event. |
| Manual memory edit | Existing repository updates content/reason by `memory_id`. | `application.edit_memory_workflow` that validates reason/content and returns `MemorySummary` plus payload-only audit event. |
| Manual memory archive | Existing repository can set archived status. | `application.archive_memory_workflow` that requires a reason and returns `MemorySummary` plus payload-only audit event. |

Recommended first implementation batch: conversation creation plus manual memory
review/edit/archive. This gives a useful minimal write surface without provider
calls, long-running workflows, source upload concerns, or schema changes.

### Candidates Requiring More Application-Service Work

These workflows are valid future API goals, but they need application-service
contracts and transaction hardening before route implementation.

| Workflow | Existing Support | Required Work Before HTTP |
| --- | --- | --- |
| Source ingest | `ingest_text_file` and `ingest_loaded_source` can create source work and chunks. | Add an HTTP-safe application service that accepts inline text or an already-loaded source object, not local filesystem paths. Define size limits, source hash/idempotency checks, duplicate handling, and response inspection. |
| Character creation | `create_character` is deterministic and validates duplicate names per source work. | Add an application wrapper with conflict mapping, explicit `character_id`, and result shape. This can follow the first batch once source-work discovery and conflict semantics are accepted. |
| Persona setup | `build_character_persona` chains reader extraction, verifier, and persona compilation. | Split or stage extraction, verification, and compilation results. Define retry/idempotency for each step and durable trace behavior on provider/validation failure. |
| Turn execution | `run_turn_workflow` wraps message persistence, context assembly, roleplay, critic, retry capture, and memory curation. | Harden provider-error and partial-persistence behavior. Decide whether critic/memory failures are fatal, warnings, or retriable follow-up work. Add request/workflow correlation from Task 05. |
| Summary generation | `summarize_conversation_workflow` wraps LLM summary and inspection. | Guarantee trace persistence on validation/provider failure, define overwrite semantics for existing summaries, and add idempotency around repeated summarization requests. |
| OOC benchmark execution | Application wrappers exist and can return run details. | Add long-running workflow policy, case validation contract, run status on partial failure, idempotency by request/workflow ID, and provider failure reporting. |
| Retrieval benchmark execution | Application wrappers exist and can return run details. | Same long-running workflow policy as OOC benchmarks, plus embedding provider failure handling and explicit retrieval case source reporting. |

### CLI-Only Or Deferred

These should not become HTTP write routes in the first write implementation
batch.

| Workflow | Defer Reason |
| --- | --- |
| Full demo workflow | It combines source ingest, character creation, persona setup, user/conversation creation, turn execution, and provider calls. Expose smaller workflow routes first. |
| Local filesystem source ingest | Batch 05 explicitly avoided local path access through HTTP. API ingest should not accept server-local paths by default. |
| Persistent audit event writes | Current audit decision is `payload_only`; no audit table, repository, migration, or retention policy exists. |
| Canon claim manual review/edit | It touches canon authority and human review semantics. Plan separately after memory writes and actor/audit boundaries are accepted. |
| Platform auth/workspace writes | Batch 06 defers full auth, workspace, membership, billing, quotas, deployment, and UI. |

## Cross-Cutting Request Contract

Every future write request should use these high-level fields where relevant:

- `request_id`: client-generated id for transport-level correlation and future
  idempotency. Required once Task 05 correlation exists.
- `actor`: local explicit actor context as defined by Task 02. Do not invent
  full auth in write-route implementation.
- `reason`: required for manual review/edit/archive and any human override.
- `metadata`: optional bounded object for client labels. It must not carry
  secrets, prompts, or hidden instructions.
- Explicit domain IDs:
  - `source_work_id`;
  - `character_id`;
  - `user_id`;
  - `conversation_id`;
  - `persona_version_id`;
  - `memory_id`;
  - `message_id` when a request acts on an existing message;
  - `context_package_id`, `critic_report_id`, `llm_trace_id`,
    `evaluation_run_id`, and `retrieval_evaluation_run_id` in responses when
    created or linked.

Routes should accept client-supplied entity IDs only when the application
service can validate collision semantics. Without an idempotency table, explicit
IDs can help safe retries for simple creates, but they do not provide complete
exactly-once guarantees for provider-backed workflows.

## Cross-Cutting Response Contract

Write responses should return a strict Pydantic model with:

- `request_id` when supplied;
- `workflow_id` once Task 05 defines it;
- `status`: `completed`, `accepted`, `failed`, or `partial`;
- `ids`: a small object listing every created or linked domain ID;
- `result`: the same inspection model family already used by read-only routes
  when practical;
- `audit_event`: payload-only audit event for manual memory operations until
  persistent audit exists;
- `warnings`: non-fatal workflow issues, such as critic or memory curation
  failures when the primary response was saved;
- `partial`: present only when status is `partial`, with `persisted_ids`,
  `failed_step`, `error_code`, and `retry_hint`.

Do not return raw provider prompts, raw trace payloads, full source chunks, or
assembled prompts from new write responses until Task 03 redaction policy is
accepted.

## Idempotency Policy

### Before An Idempotency Table Exists

Use only narrow idempotency:

- Simple create routes may accept explicit entity IDs and return `409 conflict`
  if the ID already exists with different data.
- If the ID exists with the same client-visible request data, the application
  service may return the existing record with `status=completed` and
  `idempotency.replayed=true`.
- Manual memory mutations should be idempotent only when the current state
  already matches the requested result and the same `reason` is supplied.
- Provider-backed workflows should not claim idempotency beyond request
  validation. Retrying a provider workflow may create new traces, messages,
  cases, or persona versions until a workflow/idempotency store exists.

### After Correlation/Idempotency Support Exists

Provider-backed write routes should require `request_id` or `workflow_id` and
store terminal and partial outcomes. Replays should return the stored outcome
without re-calling providers.

## Transaction And Partial-Persistence Policy

### General Session Policy

- Add a write-specific API dependency or route wrapper that commits only after
  the application service returns a successful result.
- Roll back on request validation, missing IDs, conflicts, and unexpected
  application exceptions before the success boundary.
- Application services, not route handlers, define the transaction boundary for
  multi-step workflows.
- Provider-backed workflows must document which step becomes durable before the
  next provider call starts.

### Workflow-Specific Policy

| Workflow | Transaction Boundary | Partial Persistence |
| --- | --- | --- |
| Source ingest | Parse/chunk before commit when possible; commit source work and chunks together. | If chunking fails, persist nothing. If commit fails, persist nothing. Duplicate `source_work_id` or matching source hash should map to idempotent replay or conflict. |
| Character creation | One transaction for source-work lookup and character insert. | Persist nothing on validation/conflict. Existing same character should be conflict unless an explicit idempotent replay rule matches. |
| Persona setup | Do not expose as one atomic HTTP route until staged persistence is designed. | Extraction claims/evidence, verification updates/conflicts, persona compilation, and LLM traces need step-level outcomes. A later service should either commit each completed stage with a workflow record or roll back all domain writes and still preserve failure traces. |
| Conversation creation | One transaction for user/character/persona validation and conversation insert. | Persist nothing on invalid IDs or persona mismatch. Safe to return existing conversation only under an explicit idempotent replay rule. |
| Turn execution | Needs hardened service boundary before HTTP. Primary success should mean user message, context package, and assistant message are durable. | If roleplay provider fails before assistant message, persist no user message by default. If critic/retry/memory curation fails after assistant message, return success with warnings or `partial` and include persisted IDs. Rejected assistant messages and failure cases created during retry are durable diagnostics, not errors by themselves. |
| Summary generation | One transaction for summary update after validated structured output. | On provider or validation failure, do not update `conversation.summary`. Preserve LLM trace if correlation/trace persistence supports it; otherwise defer route. |
| OOC benchmark execution | Long-running staged workflow, not first batch. | Create run with `running` or equivalent status, persist case results as completed, and mark run `completed` or `failed/partial`. Current all-at-end CLI transaction is not sufficient for HTTP. |
| Retrieval benchmark execution | Long-running staged workflow, not first batch. | Same as OOC benchmark. Empty-result and evidence-case diagnostics should remain persisted even if later cases fail. |
| Memory review/edit/archive | One transaction for memory lookup, mutation, and payload-only audit construction. | Persist nothing if validation fails. If mutation succeeds but audit payload construction fails, roll back the mutation because manual memory changes require a reasoned audit payload. |
| Audit persistence | Deferred until schema/repository exists. | Payload-only audit can be returned with the domain write. Persistent audit writes need their own atomicity rule: either audit and domain mutation commit together, or the route fails before mutation commits. |

## Workflow Contracts

### Source Ingest

Proposed route family:

- `POST /source-works`

Request expectations:

- Required: `title`, `text` or accepted source payload, `language`.
- Optional: `source_work_id`, `author`, `source_type`, `chunking`, `request_id`.
- Disallow: server-local filesystem paths in HTTP.

Response expectations:

- `source_work_id`;
- `chunk_count`;
- first/last chunk IDs or a compact chunk summary;
- `result` compatible with future source-work inspection.

Errors:

- `validation_error` for blank title/text, unsupported source type, invalid
  chunking config, or oversized payload;
- `conflict` for duplicate explicit `source_work_id` or duplicate source hash
  with different metadata;
- `unexpected_error` for storage failures.

Application prerequisites:

- Add `application.ingest_source_work` accepting loaded source content rather
  than a local path.
- Add duplicate/idempotency policy by explicit ID and preferably source hash.
- Add source-work inspection result if the API needs more than chunk counts.

### Character Creation And Persona Setup

Proposed route family:

- `POST /characters`
- Later: `POST /characters/{character_id}/persona-setup` or separate staged
  extraction/verification/persona endpoints.

Character request expectations:

- Required: `source_work_id`, `canonical_name`.
- Optional: `character_id`, `aliases`, `request_id`.

Character response expectations:

- `character_id`, `source_work_id`;
- `latest_persona_version_id=null`;
- `result` compatible with `CharacterDetail` or `CharacterSummary`.

Persona setup request expectations:

- Required: `source_work_id`, `character_id`, provider source/config reference.
- Optional: `max_chunks`, `request_id`/`workflow_id`.

Persona setup response expectations:

- `source_work_id`, `character_id`, `persona_version_id`;
- candidate claim IDs, evidence ref IDs, verified claim IDs, conflict IDs;
- trace IDs when available.

Errors:

- `not_found` for missing source work or character;
- `validation_error` for blank names, persona/source mismatch, or no verified
  claims to compile;
- `conflict` for duplicate character names;
- `provider_failure` or `provider_validation_error` for extraction,
  verification, or compilation failures;
- `partial_persistence` if a staged persona workflow has committed earlier
  claims/evidence/traces but cannot finish.

Application prerequisites:

- Add transport-neutral character creation wrapper in `application`.
- Split or harden persona setup so extraction, verification, compilation, and
  trace persistence have explicit stage outcomes.
- Decide whether persona setup replays reuse existing candidate claims or
  always creates a new extraction attempt.

### Conversation Creation

Proposed route:

- `POST /conversations`

Request expectations:

- Required: `user_id`, `character_id`.
- Optional: `conversation_id`, `persona_version_id`, `interaction_mode`,
  `request_id`.
- `persona_version_id` defaults to the latest persona for the character.

Response expectations:

- `conversation_id`, `user_id`, `character_id`, `persona_version_id`;
- `current_mode`;
- `result` compatible with `ConversationDetail` with zero messages by default.

Errors:

- `not_found` for missing user, character, or explicit persona version;
- `validation_error` when a persona belongs to another character or no persona
  exists;
- `conflict` for explicit `conversation_id` collision with different data.

Application prerequisites:

- Add `application.create_conversation_workflow`.
- Decide whether API may also create users or whether user creation remains a
  separate future route.

### Turn Execution

Proposed route:

- `POST /conversations/{conversation_id}/turns`

Request expectations:

- Required: `content`.
- Optional: `interaction_mode`, `retry_on_critic`, provider source/config
  reference, `request_id`.
- Path `conversation_id` is authoritative and must match any body ID if one is
  included.

Response expectations:

- `conversation_id`;
- `user_message_id`, `assistant_message_id`, `context_package_id`;
- `interaction_mode`;
- optional `critic_report_id`, rejected message/report IDs, failure case IDs,
  memory IDs;
- `warnings` for non-fatal critic or memory failures.

Errors:

- `not_found` for missing conversation or linked records;
- `validation_error` for blank content, invalid mode, or missing required model
  config for enabled provider roles;
- `provider_failure` for roleplay provider failures before assistant response;
- `critic_failure` when critic is configured as a required step and fails;
- `guard_failure` when memory guard is configured as a required step and fails;
- `partial_persistence` when primary messages are durable but later enrichments
  fail.

Application prerequisites:

- Harden `run_turn_workflow` into an API-ready application service with a
  primary success boundary.
- Prevent default persistence of a lone user message when roleplay generation
  fails.
- Return trace IDs and failure details without leaking redacted payloads.
- Coordinate with Task 03 redaction and Task 05 trace/workflow correlation.

### Summary Generation

Proposed route:

- `POST /conversations/{conversation_id}/summary`

Request expectations:

- Required: path `conversation_id`.
- Optional: `max_messages`, provider source/config reference, `request_id`,
  `overwrite=true`.

Response expectations:

- `conversation_id`;
- updated layered summary;
- parsed `summary_layers`;
- `llm_trace_id` when available.

Errors:

- `not_found` for missing conversation;
- `validation_error` for `max_messages < 1`, no messages to summarize, or
  overwrite not allowed;
- `provider_failure` or `provider_validation_error` for summary model failures.

Application prerequisites:

- Ensure validation-error traces are durable even when the summary is not
  updated.
- Define overwrite/idempotency semantics for repeated summary requests.

### Benchmark Execution

Proposed route family:

- `POST /eval-runs`
- `POST /retrieval-eval-runs`
- Keep dry-run/preview routes separate if implemented later.

Request expectations:

- OOC required: `character_id`; optional `persona_version_id`, `test_suite`,
  `case_suite` or explicit cases, provider source/config reference.
- Retrieval required: `character_id`; optional `source_work_id`, `test_suite`,
  explicit cases, `max_cases`, `include_empty_case`, embedding provider/config
  reference.
- Required for write execution after correlation exists: `request_id` or
  `workflow_id`.

Response expectations:

- `evaluation_run_id` or `retrieval_evaluation_run_id`;
- status and counts;
- diagnostics already used by read-only eval run details;
- case result IDs if persisted.

Errors:

- `not_found` for missing character/persona/source work;
- `validation_error` for malformed cases, duplicate case IDs, invalid limits,
  no generated cases, or persona mismatch;
- `provider_failure` for roleplay, critic, evaluator, or embedding failures;
- `partial_persistence` for runs with some completed cases.

Application prerequisites:

- Add staged run status behavior before HTTP write execution.
- Ensure case validation happens before provider calls and before run creation
  when possible.
- Store failed/partial terminal status instead of losing a started run.
- Do not reinterpret pass/fail in the API adapter.

### Memory Review/Edit/Archive

Proposed route family:

- `POST /memories/{memory_id}/review`
- `PATCH /memories/{memory_id}`
- `POST /memories/{memory_id}/archive`

Review request expectations:

- Required: `decision` (`accept` or `reject`), `reason`.
- Optional: `request_id`, local actor context from Task 02.

Edit request expectations:

- Required: `content`, `reason`.
- Optional: `request_id`, local actor context from Task 02.

Archive request expectations:

- Required: `reason`.
- Optional: `request_id`, local actor context from Task 02.

Response expectations:

- `memory_id`, `user_id`, `character_id`, optional `conversation_id`;
- updated memory summary;
- payload-only `audit_event` with before/after snapshots and `persistence`;
- `status=completed`.

Errors:

- `not_found` for missing memory;
- `validation_error` for blank reason/content, invalid decision, reviewing a
  non-candidate memory, or trying to review to a non-terminal status;
- `conflict` when an idempotent replay does not match current memory state.

Application prerequisites:

- Add memory mutation workflows in `application` so API handlers do not call
  repositories directly.
- Build audit payloads inside the same application workflow.
- Coordinate actor field shape with Task 02.

### Audit Persistence

Proposed route:

- None in the first write implementation batch.

Policy:

- Manual memory routes may return payload-only audit events.
- Do not add `POST /audit-events` until a schema, repository, retention policy,
  actor contract, and failure policy are accepted.
- Persistent audit should eventually commit atomically with the domain mutation
  it describes. If audit persistence fails, the domain mutation should fail
  before commit unless a maintainer explicitly accepts an outbox-style design.

## Error Families

Use the existing API error envelope and add stable codes before implementing
write routes:

| Code | Suggested HTTP Status | Use |
| --- | --- | --- |
| `validation_error` | 422 | Invalid request shape, invalid enum/value, blank required text, no messages to summarize, invalid cases file payload. |
| `not_found` | 404 | Missing explicit IDs: source work, character, user, conversation, persona version, memory, trace, or eval run. |
| `conflict` | 409 | Duplicate explicit ID, duplicate character name, idempotency replay mismatch, state transition conflict. |
| `provider_failure` | 502 or 503 | Provider call failed or provider unavailable before a valid structured result exists. |
| `provider_validation_error` | 502 | Provider returned data that failed Pydantic validation. Include safe trace ID when available. |
| `critic_failure` | 502 or 424 | Critic step failed when configured as required. |
| `guard_failure` | 502 or 424 | Memory guard failed when configured as required. If guard is unavailable by policy and memories become candidates, return success with warning instead. |
| `partial_persistence` | 500 or 207-style body with non-2xx status decision pending | Some records were committed before a later workflow step failed. Include `persisted_ids`, `failed_step`, and `retry_hint`. |
| `unexpected_error` | 500 | Unhandled defects. Do not leak local paths, secrets, prompts, or raw provider payloads. |

`critic_report.suggested_action=retry/log` is domain output, not automatically
an HTTP error. Memory guard rejection is domain output, not automatically an
HTTP error. Only failed infrastructure/provider/validation steps should map to
HTTP errors.

## Application-Service Prerequisites

Before implementing write routes, add or harden these application services:

1. `create_conversation_workflow(session, request)`.
2. `review_memory_workflow(session, request)`.
3. `edit_memory_workflow(session, request)`.
4. `archive_memory_workflow(session, request)`.
5. `create_character_workflow(session, request)`.
6. `ingest_source_work_workflow(session, request)` using inline/loaded content,
   not local paths.
7. API-ready turn workflow that defines primary success, warnings, partial
   result shape, and trace IDs.
8. API-ready summary workflow that preserves failure traces or defers route
   exposure until trace persistence is safe.
9. Staged benchmark workflows with durable run status and partial case results.
10. Shared write-session dependency or transaction helper for commit/rollback.
11. Expanded `normalize_error` mapping for conflict, provider failure,
    structured validation failure, and partial persistence.
12. Correlation/idempotency support from Task 05 before any provider-backed
    write route claims retry safety.

## Validation Expectations

- First write implementation should add route tests for success, validation
  error, not found, conflict/idempotency, and rollback behavior.
- Provider-backed route tests should use deterministic stub providers and cover
  provider validation failure without network access.
- Manual memory tests should assert before/after audit payloads and rollback
  when audit payload construction fails.
- Conversation creation tests should assert explicit IDs are preserved in the
  response and read-only inspection routes can fetch the created record.
- Benchmark tests should not be added until staged run status is implemented.

## Explicit Non-Goals

- No HTTP write routes in Batch 06.
- No source code, test, schema, migration, README, or VIBE changes for this
  task.
- No auth, API keys, sessions, workspaces, permissions, CORS, deployment,
  billing, quotas, or UI.
- No local filesystem path ingest over HTTP.
- No graph/vector database, LangGraph, provider-routing framework, or
  third-party memory system.
- No semantic behavior changes, prompt changes, benchmark pass/fail changes,
  retrieval changes, critic rule changes, or memory guard rule changes.
- No persistent audit table or audit-event write route until the actor/audit
  contract and schema are accepted.
- No claim/canon manual mutation API in the first write implementation batch.

## Open Questions Blocking Provider-Backed Write Routes

- What exact `workflow_id` and trace-correlation fields will Task 05 require?
- Will provider-backed HTTP workflows be synchronous only, or will they need a
  submitted/running status before completion?
- Should critic and memory curation failures after assistant message creation
  be warnings by default, or route-level errors for strict clients?
- What redaction defaults from Task 03 apply to write responses that include
  message content, context package IDs, trace IDs, or failure cases?
- Is a persistent idempotency table required before turn, summary, persona, or
  benchmark write routes are accepted?
