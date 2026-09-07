# Actor Auth Audit Boundary

Task: `plans/batch_06_api_write_readiness/02_actor_auth_audit_boundary_prompt.md`

## Current State

Batch 06 is a planning/readiness batch. It must not add auth middleware, write HTTP routes, audit
migrations, or repository code.

The current project already has the pieces needed to define a narrow local boundary:

- `User` is a local continuity identity with `id`, optional `display_name`, and `created_at`. It is
  not an authenticated account.
- Conversations and memories are already scoped by explicit `user_id` and `character_id`.
- Batch 04 added transport-neutral audit readiness models in
  `personality_jelly.application.audit`: `AuditActor`, `AuditEntity`, `AuditRelatedIds`,
  `AuditEventPayload`, and memory review/edit/archive audit event builders.
- `AuditEventPayload.persistence` is fixed to `payload_only`; there is no physical audit table,
  migration, or repository.
- The storage package does not currently have `storage/models.py`; durable schema is represented by
  `storage/orm.py`, repositories are in `storage/repositories.py`, and domain models are in
  `domain/models.py`.
- `LLMRawOutput` already stores operation, schema, provider, model, raw output, parsed output, and
  validation errors, but it does not yet carry request/workflow IDs or broad related entity IDs.
- Manual memory repository methods enforce review reasons for candidate review, allow optional edit
  reasons, and allow status changes without an archive reason. API-facing services must tighten
  that boundary before exposing manual memory mutations.

## Decision

Future local write APIs should require explicit actor context for attribution, not authentication.
The local actor boundary is:

- The write request or API dependency passes a `LocalActorContext` into application services.
- The context is used only for audit attribution, deterministic ownership checks, and debugging.
- The context must not be treated as proof of identity, permission, tenant membership, billing
  subject, or rate-limit subject.
- API handlers remain thin adapters; ownership validation, workflow execution, and audit payload
  creation belong in `personality_jelly.application` or lower service modules.

## Minimum Local Actor Model

Later implementation should add an application-level actor input model before adding write routes.
It should map cleanly onto the existing `AuditActor` payload shape:

| Field | Required | Contract |
| --- | --- | --- |
| `actor_type` | yes | Use existing values. Local API writes should normally use `api_user`; CLI service callers use `cli_user`; internal non-user workflow steps use `system`; provider calls use `provider` only when the provider itself is the entity being audited. Do not use `workspace_member` until platform auth exists. |
| `actor_id` | yes | Nonblank stable local attribution ID. For self-service local writes this may equal `user_id`; for local operator actions use a synthetic ID such as `local-operator:<name>` or `api-local:<label>`. |
| `actor_label` | no | Human-readable display label for local logs/responses. Store in audit metadata until the audit model grows a first-class field. Do not use it for lookup or authorization. |
| `user_id` | workflow-dependent | Domain continuity subject. Required for user-owned workflows such as conversation create, turn execution, and memory mutation. It may differ from `actor_id` for operator review. |
| `request_reason` | workflow-dependent | Required for manual semantic-state changes; optional for mechanical creation workflows. Audit events still need a nonblank `reason`, generated from the workflow intent when no caller reason is required. |
| `request_id` / `workflow_id` | future-ready | Should be accepted once Task 05 correlation is implemented. Until then, place caller-supplied values in audit metadata only if available. |

Do not resolve local actors by `display_name`. Do not infer actors from network address, process
user, CORS origin, local filesystem path, provider config, or API key placeholder.

## Deferred Auth And Platform Concerns

These are explicitly outside the current phase:

- login, logout, sessions, cookies, OAuth/OIDC, external accounts, password storage, account
  linking, or user profiles beyond the existing local `User`;
- API keys, service tokens, bearer token validation, request signing, CORS policy, deployment
  hardening, or server process management;
- workspace tables, workspace membership, roles, RBAC/ABAC, tenant isolation, org/project scoping,
  billing, quotas, rate limits, retention policy, legal/compliance export, or admin dashboards;
- permission checks beyond deterministic local ownership validation already implied by IDs;
- broad prompt/message/trace visibility policy, which belongs to Batch 06 redaction planning and a
  later implementation batch.

Later platform auth can map an authenticated principal into the same `LocalActorContext` boundary by
setting `actor_type=workspace_member` or another accepted platform type and preserving the same
application service contract.

## Audit Event Contract

Every future persisted audit event should preserve the Batch 04 payload shape and add only the
minimum persistence/correlation fields needed by later implementation:

| Field | Contract |
| --- | --- |
| `id`, `created_at` | Generated by the audit layer; append-only. |
| `actor` | Existing `AuditActor` with `actor_type` and `actor_id`. Local labels stay in metadata until modeled. |
| `operation` | Stable action name, e.g. `source.ingest`, `character.create`, `persona.compile`, `conversation.create`, `conversation.turn`, `conversation.summarize`, `memory.review`, `memory.edit`, `memory.archive`, `benchmark.run`, `audit.persist`. |
| `entity` | Primary affected entity. Use the durable entity ID after success; for pre-persistence failure, use the requested entity ID or a generated workflow ID when Task 05 defines it. |
| `related_ids` | Fill all known IDs from `AuditRelatedIds`: `source_work_id`, `character_id`, `user_id`, `conversation_id`, `message_id`, `context_package_id`, `persona_version_id`, `critic_report_id`, `llm_trace_id`, `evaluation_run_id`, and `retrieval_evaluation_run_id`. |
| `reason` | Nonblank. Human/manual semantic mutations require caller-supplied reason. Mechanical workflow events may use deterministic service reasons such as `local API source ingest requested`. |
| `before` / `after` | Compact structured snapshots for manual mutation and status changes. Do not copy raw prompts, provider secrets, full source chunks, or stack traces into audit snapshots. |
| `metadata.result` | Required until a first-class `result` field exists. Use `succeeded`, `failed`, `partial`, `rejected`, or `retried`; include normalized error code/family when failed. |
| `metadata.request_id` / `metadata.workflow_id` | Optional until Task 05 establishes first-class correlation fields. |
| `persistence` | `payload_only` until an audit migration/repository exists; later persisted rows should keep the same event payload semantics. |

Audit events explain state changes. They must not become canon, persona, accepted memory, or current
business state.

## Audit Expectations By Workflow

| Future workflow | Audit required | Minimum actor/entity/action/reason/result fields | Payload-only enough? |
| --- | --- | --- | --- |
| Source ingest | Required for future API write route. | Actor context; entity `source_work:<source_work_id>` after success or workflow ID on failure; operation `source.ingest`; related `source_work_id`; reason from request or deterministic ingest intent; result `succeeded`, `failed`, or `partial`; metadata with source type, chunk count, sanitized validation/provider error family. | Payload-only is acceptable only for a local experimental route that returns the event in the response and documents no durable audit history. Persisted audit should exist before broad API exposure. |
| Character create | Required. | Actor; entity `character:<character_id>`; operation `character.create`; related `source_work_id`, `character_id`; reason from request/intent; result. | Payload-only acceptable for local-only first pass; persisted audit preferred before broad client use. |
| Character/persona setup | Required because it invokes Reader, Verifier, and persona compiler and can create claims, evidence, conflicts, and persona versions. | Actor; entity `persona_version:<persona_version_id>` or `character:<character_id>` on failure; operation `character_persona.setup` with child steps `reader.extract`, `verifier.verify`, `persona.compile` in metadata; related `source_work_id`, `character_id`, `persona_version_id`, and available `llm_trace_id` values; result and partial counts. | Schema persistence should exist before exposing this as a write API because partial semantic writes need durable review history. |
| Conversation create | Required. | Actor; entity `conversation:<conversation_id>`; operation `conversation.create`; related `user_id`, `character_id`, `persona_version_id`, `conversation_id`; reason/intent; result. | Payload-only acceptable for a narrow local route if the response includes the audit payload. |
| Turn execution | Required. | Actor; entity `conversation:<conversation_id>` or assistant `message:<message_id>`; operation `conversation.turn`; related `user_id`, `character_id`, `conversation_id`, user/assistant message IDs, `context_package_id`, `critic_report_id`, memory IDs in metadata, failure case IDs in metadata, and available `llm_trace_id` values; reason/intent; result with retry/partial state. | Persisted audit should exist before public/broad API exposure because turns can partially persist messages, context packages, critic reports, failure cases, and memories. |
| Summary generation | Required because it mutates `Conversation.summary`. | Actor; entity `conversation:<conversation_id>`; operation `conversation.summarize`; related `user_id`, `character_id`, `conversation_id`, and available summary `llm_trace_id`; before/after summary metadata should be compact or redacted; result. | Payload-only acceptable only for CLI/local service parity; persisted audit should precede write API exposure. |
| OOC benchmark execution | Required for future API run endpoint. | Actor; entity `evaluation_run:<run_id>`; operation `benchmark.ooc.run`; related `character_id`, `persona_version_id`, `evaluation_run_id`, message/context/critic IDs as available; reason/intent; result with passed/failed counts. | Payload-only may be acceptable for local diagnostics; persisted audit should be added before clients rely on run history governance. |
| Retrieval benchmark execution | Required. | Actor; entity `retrieval_evaluation_run:<run_id>`; operation `benchmark.retrieval.run`; related `source_work_id`, `character_id`, `retrieval_evaluation_run_id`; reason/intent; result with recall/pass diagnostics and sanitized provider failure family. | Payload-only may be acceptable for local diagnostics; persisted audit should be added before broad API exposure. |
| Manual memory review | Required before any API/UI-facing operation. | Actor; entity `memory:<memory_id>`; operation `memory.review`; related `user_id`, `character_id`, optional `conversation_id`; caller reason required; before/after snapshots include memory `scope`, `status`, `content`, `importance`, and `reason`; result. | Existing Batch 04 payload builders are enough for service-layer readiness. Persisted audit is required before exposing through API/UI. |
| Manual memory edit | Required before API/UI-facing operation. | Actor; entity `memory:<memory_id>`; operation `memory.edit`; related memory owner IDs; caller reason required; before/after snapshots include same identity/scope and changed content/reason; result. | Existing payload builders are enough for readiness. Persisted audit required before API/UI exposure. |
| Manual memory archive | Required before API/UI-facing operation. | Actor; entity `memory:<memory_id>`; operation `memory.archive`; related memory owner IDs; caller archive reason required; before/after status transition to `archived`; result. | Existing payload builder exists, but application service and repository usage must enforce archive reason before API/UI exposure. Persisted audit required. |
| Canon claim review/correction | Required before human claim review APIs. | Actor; entity `canon_claim:<claim_id>`; operation `canon_claim.review`; related `source_work_id`, `character_id`, evidence IDs in metadata, and available verifier `llm_trace_id`; caller reason required; before/after status/confidence/reasoning; result. | Payload-only is not enough for API exposure. Needs persisted audit and application service because canon changes affect verified source-backed state. |
| Failure-case or benchmark review | Required before manual triage APIs. | Actor; entity `failure_case:<id>` or evaluation case/run ID; operation `failure_case.review` or `benchmark.review`; related conversation/message/context/critic/eval IDs; caller reason required; before/after disposition metadata; result. | Needs persisted audit before API exposure because these are human governance decisions. |
| Audit persistence itself | Required when an audit event fails to persist after domain mutation. | Actor `system` or original actor; entity `audit_event:<event_id>` or workflow ID; operation `audit.persist`; reason `audit persistence outcome`; result `failed` or `succeeded`; sanitized error code. | Not applicable. This requires the audit table/repository and a clear transaction policy. |

## Manual Memory Boundary

Future application services for manual memory mutation should be created before API routes:

- `review_memory_candidate(session, memory_id, status, reason, actor_context)`
- `edit_memory(session, memory_id, content, reason, actor_context)`
- `archive_memory(session, memory_id, reason, actor_context)`

Those services must:

- require nonblank actor context and nonblank caller reason for review, edit, and archive;
- load the memory before mutation and preserve `id`, `user_id`, `character_id`, `conversation_id`,
  and `scope` across before/after snapshots;
- allow review only from `candidate` to `accepted` or `rejected`;
- archive by changing status to `archived` without changing ownership or scope;
- return both the updated memory summary and an `AuditEventPayload`;
- persist the audit event in the same transaction once audit persistence exists;
- keep accepted user/relationship memory separate from canon and persona state.

Repository methods can remain low-level primitives, but API-facing services must not call
`MemoryRepository.update_status` for archive without a reason.

## Provider Failure And Retry Audit

Provider-invoking workflows must record enough to debug outcomes without leaking secrets.

Audit metadata may include:

- provider role, e.g. `roleplay`, `critic`, `memory_curator`, `mode_classifier`, `retriever`,
  `reader`, `verifier`, `persona_compiler`, `benchmark_evaluator`;
- `provider_name`, `model_name`, operation name, schema name, validation error count, and
  `llm_trace_id` when a trace row exists;
- retry count, retry policy, rejected assistant message ID, rejected critic report ID, final
  assistant message ID, failure case IDs, and final result;
- normalized error code/family such as `provider_error`, `validation_error`, `guard_rejected`,
  `critic_retry`, `partial_write`, or `unexpected_error`.

Audit metadata must not include:

- API keys, environment variable values, provider base URLs that may reveal private deployments,
  auth headers, request signing material, local filesystem paths, raw stack traces, or raw provider
  config;
- raw prompts, assembled prompts, full source chunks, raw messages, raw provider outputs, or full
  validation payloads. Those should stay in their existing domain/trace records and be governed by
  the Batch 06 redaction policy.

If a provider call fails before `LLMRawOutput` can be recorded, the audit event should store only a
sanitized error family, provider role, provider/model labels if known, and result `failed`.

## Schema, Repository, And Service Prerequisites

Before durable audit persistence or write APIs are implemented:

1. Add an append-only `audit_events` migration using the in-repo `schema_migrations` system.
2. Add an `AuditEvent` domain/storage shape or persist `AuditEventPayload` with equivalent columns:
   `id`, `created_at`, actor fields, operation, entity fields, related IDs, reason, before/after
   JSON, metadata JSON, result, and persistence/version fields.
3. Add an `AuditEventRepository` with append-only `add`, `get`, and list/filter methods. Do not add
   update/delete behavior.
4. Add indexes for `created_at`, `operation`, `actor_type/actor_id`, `entity_type/entity_id`, and
   high-value related IDs such as `user_id`, `character_id`, `conversation_id`, `llm_trace_id`,
   `evaluation_run_id`, and `retrieval_evaluation_run_id`.
5. Add application services that accept actor context and return result models with audit payloads
   for manual memory review/edit/archive, source ingest, character/persona setup, conversation
   create, turn execution, summary generation, and benchmark execution.
6. Decide transaction policy: for mandatory audit workflows, domain mutation and audit insertion
   should commit together; if audit insertion fails after a mutation, the service should roll back
   or return a documented `partial` result only where the workflow already permits partial
   persistence.
7. Extend audit payload or metadata conventions for `request_id` and `workflow_id` after Task 05
   finalizes correlation.
8. Keep API routes as adapters that validate request models, acquire sessions, pass actor context
   to application services, and map normalized errors. Do not write audit rows directly in API
   handlers.
9. Add redaction-aware audit response models before exposing audit events through HTTP inspection.

## Future Platform Compatibility Boundary

This local design leaves room for platform auth without implementing it now:

- `actor_id` remains an opaque string, so future account/member IDs can map into it without
  rewriting domain workflows.
- `actor_type=workspace_member` remains reserved until a real workspace membership model exists.
- Optional future `workspace_id` should be added as a nullable related field or metadata field only
  when workspace ownership is implemented. Do not fake workspace scope in current local routes.
- `user_id` remains the conversation/memory continuity subject, not the authentication principal.
  Platform auth can later decide whether an account may act for a `user_id`.
- Existing explicit IDs (`source_work_id`, `character_id`, `persona_version_id`, `conversation_id`,
  memory IDs, trace IDs, and eval IDs) stay visible in service contracts so later tenant/workspace
  policy can validate ownership deterministically.

## Validation Expectations

Later implementation should add focused tests for:

- actor context validation rejects blank `actor_id`, invalid `actor_type`, and missing required
  `user_id` for user-owned workflows;
- manual memory review/edit/archive require reason and preserve memory identity, owner IDs, and
  scope across snapshots;
- provider failure/retry audit metadata omits secrets and raw prompts while preserving trace IDs and
  failure families;
- audit persistence is append-only and transactionally tied to mandatory write workflows;
- API route tests assert that write handlers pass actor context to application services instead of
  constructing audit details in HTTP code.

No automated tests are required for this planning-only task.

## Open Implementation Blockers

- The project needs an accepted audit persistence migration/repository before API/UI-facing manual
  memory mutation or canon review routes are safe.
- Task 05 must settle request/workflow/LLM trace correlation before audit rows should claim
  first-class workflow IDs.
- Batch 06 redaction policy must settle which audit fields can be returned by HTTP inspection
  endpoints before audit event listing is exposed.
- A coordinator should reconcile this document with Task 01 write workflow transaction policy
  before selecting the first write implementation batch.
