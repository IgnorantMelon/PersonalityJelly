# Provider-Backed Write Contract Matrix

Batch 09 Task 03 reconciles the source ingest and character/persona setup contracts into shared
write-route conventions for the next implementation batch. This is a planning artifact only. It
does not implement routes, schemas, migrations, tests, provider behavior, or source logic.

## Inputs Reconciled

- `01_source_ingest_api_contract.md`
- `02_character_persona_setup_api_contract.md`
- `plans/batch_08_api_workflow_persistence/BATCH_08_CLOSEOUT.md`
- Current Batch 08 application/API foundations:
  - `WriteResponseEnvelope` over `WorkflowResponseSummary`;
  - `CorrelationContext`, `WorkflowContext`, `WorkflowRelatedIds`, and persisted workflow links;
  - `Idempotency-Key` plus optional body `idempotency_key` matching;
  - normalized `provider_failure`, `provider_validation_error`, `partial_persistence`,
    `retryable_conflict`, `guard_failure`, and `critic_failure` families;
  - read-only `/audit-events` and `/workflow-runs` inspection routes with recursive redaction.

## Reconciled Recommendation

Implement the first API implementation batch in this order:

1. `POST /source-works`
2. `POST /characters`
3. `POST /characters/{character_id}/persona-setup-runs`

The first implementation candidate should be `POST /source-works`.

Reasoning:

- It creates the durable prerequisite for every later character/persona setup workflow:
  `source_work_id` and `source_chunk` rows.
- It is deterministic in the accepted contract: no LLM provider, embedding provider, prompt, trace,
  or partial business persistence.
- It exercises the Batch 08 write foundation that every later provider-backed route needs:
  workflow run, workflow links, persistent audit, idempotency replay/conflict, redacted response, and
  diagnostic inspection.
- It avoids combining source creation with character/persona setup, which would make retries and
  partial persistence harder to reason about.

`POST /characters` should follow as a small deterministic bridge. The first true provider-backed
route should be `POST /characters/{character_id}/persona-setup-runs`, but only after its staged
application service can persist completed setup stages and normalize partial outcomes.

## Explicit Reconciliation Choices

| Topic | Source ingest contract | Character/persona contract | Chosen convention |
| --- | --- | --- | --- |
| Route shape | Resource create route `POST /source-works`; no `source-ingestions` yet. | Deterministic `POST /characters`; provider setup as `POST /characters/{character_id}/persona-setup-runs`. | Use resource routes for deterministic resource creation and `*-runs` routes for staged provider workflows. Do not create generic ingestion/run resources unless async or staged provider behavior needs them. |
| First implementation | Source ingest first. | Character create plus setup split; setup not first until staged prerequisites exist. | Source ingest first, then character create, then persona setup. This sequence is grounded in prerequisites and retry complexity. |
| Idempotency | Required for source ingest. | Required for persona setup; optional for deterministic character create. | Required for source ingest and all provider-backed routes. Optional but supported for deterministic bridge routes only when existing helpers can store a replay safely. |
| Status mapping | Source success `201`; no provider failures; partial not valid. | Setup success `201`; provider and partial failures normalized. | Use common mappings below. Partial persistence is only valid after durable business/domain rows have committed before a later failure. |
| `WorkflowRelatedIds` breadth | May need `source_chunk_ids`; otherwise use result and workflow links. | May need claim/evidence/conflict IDs; otherwise use result and workflow links. | Keep `WorkflowRelatedIds` for shared high-value IDs and lists already present; use workflow links as authoritative for route-specific many-ID lists unless a focused implementation expands the model. |
| Audit volume | One audit event for source ingest. | One terminal audit event for setup; step audit deferred. | Persist one terminal audit event per write workflow by default. Step-level debugging belongs in workflow links and trace IDs until audit volume proves useful. |
| Raw response detail | No source text or chunks in write response. | No claim text, evidence excerpts, prompts, provider payloads, or persona rules by default. | Default write responses return IDs, counts, statuses, timestamps, and redaction booleans. Debug exposure must use read-only inspection under an explicit policy, not write response expansion. |

## Common Route Naming

| Route kind | Convention | Examples | Notes |
| --- | --- | --- | --- |
| Deterministic resource create | `POST /{resources}` | `POST /source-works`, `POST /characters`, existing `POST /conversations` | Use when success creates the named durable resource synchronously and all business rows can commit atomically. |
| Deterministic mutation on existing resource | `POST` or `PATCH` under the existing resource | existing `POST /memories/{memory_id}/review`, `PATCH /memories/{memory_id}` | Use existing local-first mutation style. Require actor/reason when the operation changes reviewed state. |
| Provider-backed staged workflow | `POST /{resources}/{id}/{workflow-name}-runs` | `POST /characters/{character_id}/persona-setup-runs` | Use when the operation can fail after traces or domain rows have persisted, or may later become async. |
| Combined convenience workflow | Deferred route, not first implementation | `POST /character-persona-setup-runs` | Defer until separate source, character, and setup routes prove replay and partial semantics. |

Path IDs are authoritative. If the body repeats a path ID, it must match after normalization or the
route returns `422 validation_error`. Do not use server-local file paths, raw provider config, raw
prompt controls, or hidden semantic options as route inputs.

## Common Write Response Envelope

All new write responses use the existing envelope shape:

```json
{
  "request_id": "req_...",
  "workflow_id": "wf_...",
  "workflow_type": "source_work.ingest",
  "status": "completed",
  "ids": {
    "source_work_id": "sw_...",
    "character_id": "char_...",
    "persona_version_id": "persona_...",
    "audit_event_id": "audit_...",
    "audit_event_ids": ["audit_..."],
    "llm_trace_ids": []
  },
  "result": {},
  "warnings": []
}
```

Rules:

- `request_id` is always returned.
- `workflow_id` is returned once the application service starts.
- `workflow_type` is dot-qualified and matches the idempotency scope and audit operation unless a
  route intentionally documents a narrower audit step.
- `status` is one of `running`, `completed`, `failed`, or `partial` in persisted workflow records.
  Synchronous success responses normally return `completed`.
- `ids` carries shared related IDs from `WorkflowRelatedIds`.
- Route-specific many-ID lists may live in `result.persisted_ids` and workflow links when
  `WorkflowRelatedIds` does not yet have the field.
- `warnings` are for non-fatal issues only. Provider step failures that stop the requested workflow
  are errors, not warnings.
- `result` is route-specific and must be safe under the default redaction profile.

## Common Error Envelope

Keep the current API error envelope:

```json
{
  "error": {
    "code": "provider_validation_error",
    "message": "Provider output failed schema validation",
    "details": {
      "correlation": {
        "request_id": "req_...",
        "workflow_id": "wf_...",
        "workflow_type": "character_persona.setup",
        "status": "failed",
        "ids": {},
        "failed_step": "reader_extract"
      },
      "failed_step": "reader_extract",
      "persisted_ids": {},
      "llm_trace_ids": ["llmraw_..."],
      "audit_event_ids": ["audit_..."],
      "retry_hint": "retry_with_new_idempotency_key"
    },
    "trace_id": "llmraw_..."
  }
}
```

Rules:

- Until the error schema is intentionally migrated, put request/workflow correlation under
  `error.details.correlation`.
- `trace_id` may contain one representative `llm_trace_id` only. Do not put `request_id` or
  `workflow_id` in `trace_id`.
- Validation before workflow start may include only `request_id`.
- Provider, partial, guard, and critic/follow-up failures include `workflow_id`, `workflow_type`,
  `failed_step`, `persisted_ids`, trace IDs, audit IDs, and a retry hint when available.
- Error details must pass the shared sanitizer and must not include raw request bodies, source text,
  prompt text, provider payloads, stack traces, SQL, local paths, secrets, or conflicting payloads.

## Common Status And Error Codes

| HTTP | Error code | Applies to | Convention |
| --- | --- | --- | --- |
| 201 | n/a | New synchronous create/workflow success. | Return the write envelope and store the same redacted payload for replay when idempotency is active. |
| 200 | n/a | Optional future no-op mutation success. | Do not use for first source ingest, character create, or persona setup success. |
| 202 | n/a | Future async accepted workflow. | Deferred. Do not return `accepted` until polling and terminal replay contracts exist. |
| 400 | `validation_error` | Malformed body only if a route explicitly maps it. | Current FastAPI validation path generally returns 422. |
| 404 | `not_found` | Missing explicit source, character, user, conversation, persona, memory, audit, workflow, trace, or eval ID. | Do not use for inline source ingest unless a future source reference is added. |
| 409 | `conflict` | Duplicate explicit ID, duplicate character name in source, idempotency hash mismatch, state transition conflict. | Details may include safe IDs and `conflict=request_hash_mismatch`; never include the conflicting request body. |
| 409 | `retryable_conflict` | In-progress or crashed workflow under the same idempotency scope/key, or retry conflict that should be inspected first. | Current workflow failure mapper supports 409 for this family. Include `retry_hint=inspect_workflow_run`. |
| 413 | `validation_error` | Oversized inline source content. | Accept only if the implementation adds a shared mapper; otherwise use 422 and document the follow-up. |
| 422 | `validation_error` | Invalid request shape, blank fields, missing actor, missing required idempotency key, body/header mismatch, forbidden path fields, source/character mismatch, unsupported options. | Persist nothing unless the application service already started a workflow for a documented preflight failure. |
| 500 | `partial_persistence` | Business/domain rows committed before a later required step failed. | Current mapper uses 500. Include persisted IDs and retry/review hint. |
| 500 | `unexpected_error` | Sanitized unhandled storage or code defects. | Do not leak exception bodies, paths, SQL, stack traces, prompts, source, or provider payloads. |
| 502 | `provider_failure` | Provider timeout, unavailable provider, transport failure, or required provider call failed before usable structured output. | Current mapper uses 502 for provider workflow failures. A later 503 distinction requires mapper and tests. |
| 502 | `provider_validation_error` | Provider output failed Pydantic validation or contains invalid semantic references. | Include safe trace IDs if traces were persisted. |
| 502 | `guard_failure` | Required guard follow-up failed before the route can safely complete. | Future turn/memory workflows only; not valid for source ingest or persona setup unless a guard step is added. |
| 502 | `critic_failure` | Required critic or follow-up critic step failed. | Future turn workflows only; critic domain suggestions are not automatically HTTP errors. |

Do not use `207 Multi-Status` for partial persistence. The accepted current shape is a non-2xx error
with `code=partial_persistence` and persisted IDs.

## Audit Contract

Audit operation names use the same dot-qualified style as workflow types:

| Workflow | Audit operation | Entity | Result values | Notes |
| --- | --- | --- | --- | --- |
| Source ingest | `source_work.ingest` | `source_work` | `succeeded`, `failed` | One terminal event. `failed` only after workflow start; pre-validation may persist nothing. |
| Character create | `character.create` | `character` | `succeeded`, `failed` | One terminal event if the workflow starts. |
| Persona setup | `character_persona.setup` | `character` | `succeeded`, `failed`, `partial` | One terminal event. Step audit operations are deferred. |

Common audit rules:

- `actor` is a `LocalActorContext`; it is local attribution, not auth.
- Default `actor_type` for API writes is `api_user` unless the application service uses `system`
  for internal terminal failure events.
- `reason` comes from `actor.operation_reason` or a route-specific fallback.
- `related_ids` should include every supported first-class ID known to `AuditRelatedIds`:
  `source_work_id`, `character_id`, `user_id`, `conversation_id`, `memory_id`,
  `persona_version_id`, representative `llm_trace_id`, eval IDs, and retrieval eval IDs.
- Additional many-ID lists, such as source chunks, claims, evidence refs, conflicts, and multiple
  traces, go in sanitized audit metadata and workflow links.
- `before` and `after` snapshots must be compact and safe. Source ingest `after` contains metadata
  and counts only. Persona setup `after` contains IDs/counts/statuses only.
- Audit metadata includes request/workflow IDs, workflow type/status, failed step, counts, retry
  hint, and redaction markers.
- Audit metadata never includes raw source text, chunk text, evidence excerpts, prompts, provider
  payloads, trace payloads, secrets, local paths, SQL, or stack traces.

## Workflow Types, Steps, Links, And Persisted IDs

### Workflow Types

| Route | Workflow type | Provider-backed | Terminal statuses |
| --- | --- | --- | --- |
| `POST /source-works` | `source_work.ingest` | No | `completed`, `failed` |
| `POST /characters` | `character.create` | No | `completed`, `failed` |
| `POST /characters/{character_id}/persona-setup-runs` | `character_persona.setup` | Yes | `completed`, `failed`, `partial` |

### Provider Setup Step Names

Use stable snake-case step names:

- `setup_preflight`
- `reader_extract`
- `verifier_validate`
- `persona_compile`
- `terminal_audit`
- `idempotency_record`

Future provider-backed routes should follow this style: noun or role plus verb, for example
`roleplay_generate`, `critic_evaluate`, `memory_curate`, `memory_guard`, `summary_generate`, and
`benchmark_case_evaluate`.

### Link Relations

| Relation | Meaning | Examples |
| --- | --- | --- |
| `input` | Existing durable record used as workflow input. | source work, character, conversation, persona version. |
| `created` | New durable domain/diagnostic record created by the workflow. | source chunk, canon claim, evidence ref, claim conflict, message, failure case. |
| `updated` | Existing durable record changed by the workflow. | canon claim verification status, memory mutation. |
| `result` | Primary output record of the workflow. | persona version, eval run. |
| `trace` | Persisted provider/LLM trace record. | `llm_trace`. |
| `audit` | Persistent audit event for the workflow. | `audit_event`. |
| `idempotency` | Stored replay/conflict record. | `idempotency_record`. |

Do not invent route-specific synonyms such as `subject`, `owner`, or `output` for new provider
contracts. Existing older links may keep their current values, but new Batch 10 routes should use
the relations above for consistency.

### Persisted-ID Shape

`ids` should use `WorkflowRelatedIds` where possible:

- `source_work_id`
- `character_id`
- `user_id`
- `conversation_id`
- `persona_version_id`
- `audit_event_id`
- `audit_event_ids`
- `llm_trace_ids`

Route-specific many-ID lists should be returned under `result.persisted_ids` and represented through
workflow links unless a focused implementation expands `WorkflowRelatedIds`:

```json
{
  "result": {
    "persisted_ids": {
      "source_chunk_ids": ["chunk_..."],
      "candidate_claim_ids": ["claim_..."],
      "verified_claim_ids": ["claim_..."],
      "evidence_ref_ids": ["evidence_..."],
      "claim_conflict_ids": ["conflict_..."]
    }
  }
}
```

The persisted workflow run `persisted_ids` JSON should be compact and redacted. It can contain the
same ID lists when practical, but workflow links are the authoritative complete relation set.

## Idempotency Contract

### Location And Matching

| Route | Required | Location | Matching rule |
| --- | --- | --- | --- |
| `POST /source-works` | Yes | `Idempotency-Key` header; optional body mirror `idempotency_key` | Header and body must match after normalization. |
| `POST /characters` | Optional in first implementation | Same | If present, use replay/conflict helpers. |
| `POST /characters/{character_id}/persona-setup-runs` | Yes | Same | Header and body must match; path `character_id` participates in request hash. |

`X-Request-ID` is optional for all write routes. If both header and body `request_id` are present,
they must match. If omitted, the API generates `req_...`.

### Request Hash

Use the existing canonical JSON SHA-256 request hash helper. Exclude:

- `request_id`
- `idempotency_key`
- generated IDs and timestamps

Include:

- route path IDs that affect behavior, such as `character_id`;
- all body fields that affect domain writes, audit metadata, provider selection aliases, or workflow
  options;
- actor context and sanitized metadata that materially affect audit output;
- full inline source content for source ingest, but store only the digest.

### Replay Payload

Replay returns the originally stored response status code and the exact stored redacted payload:

- success replay returns the write envelope;
- failed or partial provider-backed replay returns the stored error envelope;
- replay does not create new domain rows, workflow runs, workflow links, audit events, traces, or
  idempotency records;
- replay does not call providers;
- replay payloads must not contain raw source text, prompt text, provider payloads, local paths,
  secrets, trace payloads, or raw request bodies.

### Conflict Behavior

- Same idempotency key and same request hash: replay.
- Same idempotency key and different request hash: `409 conflict`.
- Existing explicit entity ID with different request data: `409 conflict`.
- Running workflow with the same idempotency scope/key and no terminal replay payload:
  `409 retryable_conflict` with `retry_hint=inspect_workflow_run`.
- Partial terminal outcome under the same key: replay the same partial payload; do not resume.
- A new attempt uses a new idempotency key. Automatic resume and reuse of prior setup rows are
  deferred.

## Redaction Defaults

Use the safe API default for every new write route. New write routes must not copy the older
local-MVP raw inspection exposure.

Default write responses may expose:

- IDs, counts, enum/status labels, timestamps, language/source type, provider role aliases if safe,
  and model aliases if the active profile allows them;
- redaction booleans such as `text_redacted=true`, `source_preview_redacted=true`,
  `prompt_redacted=true`, and `trace_payload_redacted=true`;
- `llm_trace_ids` for follow-up inspection.

Default write responses must never expose:

- API keys, bearer tokens, cookies, auth headers, environment secret values, session tokens, or
  credentials;
- raw provider config, provider base URLs, provider headers, raw provider requests/responses, or
  provider error bodies;
- raw prompts, assembled prompts, prompt compatibility instructions, system/developer messages, or
  raw chat payloads sent to a provider;
- raw source content, source chunk text, source previews, evidence excerpts, or full retrieved
  chunks;
- claim reasoning, raw persona rules, persona prompt fragments, or compiled persona text by
  default;
- raw user message text, memory content, memory reasons, summaries, relationship notes, or
  reflective notes in provider-backed write results;
- `LLMRawOutput.raw_output`, `parsed_output`, `response_schema`, `validation_errors`, or arbitrary
  trace payloads;
- local filesystem paths, database URLs, SQL statements, stack traces, exception bodies, raw request
  bodies, or conflicting request bodies.

Rejected path-like input should fail validation before workflow start when possible. Sanitizers
remain required as a defense for nested metadata, warnings, audit metadata, workflow errors, and
idempotency replay payloads.

## Failure Shape Matrix

### Provider Failure

Use when a required provider call fails before a valid structured result is available.

```json
{
  "error": {
    "code": "provider_failure",
    "message": "Provider call failed",
    "details": {
      "error_family": "provider_failure",
      "error_code": "provider_timeout",
      "failed_step": "reader_extract",
      "workflow_id": "wf_...",
      "persisted_ids": {},
      "llm_trace_ids": [],
      "audit_event_ids": ["audit_..."],
      "retry_hint": "retry_with_new_idempotency_key",
      "correlation": {}
    },
    "trace_id": null
  }
}
```

For persona setup before Reader domain rows commit, workflow status is `failed`. After business rows
commit, the exposed family becomes `partial_persistence` with
`details.error_code=provider_failure`.

### Provider Validation Failure

Use when provider output exists but fails Pydantic validation or contains invalid semantic
references, such as unknown chunk IDs or claim IDs.

Required details:

- `error_family=provider_validation_error`;
- stable `error_code`, for example `schema_validation_failed` or `invalid_provider_reference`;
- `failed_step`;
- safe `llm_trace_ids` when trace rows exist;
- no raw output, parsed output, validation payload, source text, or prompts.

Before business rows commit, return `502 provider_validation_error`. After business rows commit,
return `500 partial_persistence` with `details.error_code=provider_validation_error`.

### Partial Persistence

Use when any business/domain row was committed before a later required step failed.

Required details:

- `error_family=partial_persistence`;
- `error_code` naming the cause, such as `provider_failure`, `provider_validation_error`,
  `no_verified_claims`, `terminal_audit_failed`, or `idempotency_record_failed`;
- `failed_step`;
- `workflow_id`;
- `persisted_ids`;
- `llm_trace_ids`;
- `audit_event_ids`;
- `retry_hint`.

For persona setup, accepted partial states are:

| State | Failed step | Persisted IDs | Retry hint |
| --- | --- | --- | --- |
| `workflow_failed_no_domain` | `setup_preflight` or `reader_extract` | workflow, optional traces/audit only | Fix request/provider config and retry with a new key. |
| `reader_persisted_verifier_failed` | `verifier_validate` | candidate claims, evidence refs, Reader traces | Inspect workflow/trace IDs, then retry with a new key or future resume route. |
| `verification_persisted_no_verified_claims` | `persona_compile` precondition | candidate/verified/rejected claim status, evidence refs, conflicts | Review source/name/aliases or add manual claim review; do not auto-compile. |
| `verification_persisted_compiler_failed` | `persona_compile` | candidate/verified claims, evidence refs, conflicts, compiler trace if present | Retry with a new key after provider issue is resolved. |
| `terminal_commit_failed` | `terminal_audit` or `idempotency_record` | prior setup rows; no persona ID if persona rolled back | Operator investigation; replay may not exist. |

Do not delete, merge, or overwrite partially persisted canon rows automatically.

### Retryable Conflict

Use when the retry cannot safely proceed but the client may inspect and retry later:

- idempotency scope/key has a `running` workflow without terminal replay;
- a workflow crashed after starting but before terminal idempotency storage;
- a future resume route is required before continuing.

Return `409 retryable_conflict` with safe `workflow_id`, `workflow_type`, existing
`idempotency_record_id` if available, and `retry_hint=inspect_workflow_run`.

### Guard Failure

Guard failure is a future turn/memory workflow family, not part of source ingest or persona setup
unless a route explicitly adds a guard step.

Use `guard_failure` only when a required guard step fails and the route cannot safely complete.
If the accepted policy says guard-unavailable memories remain `candidate`, return success with a
warning instead of an HTTP error.

Guard failure details follow provider failure details and must include:

- `failed_step=memory_guard` or a route-specific guard step;
- `persisted_ids` showing any durable message/memory/context rows;
- `retry_hint`;
- no raw memory content, user text, prompts, or provider payloads.

### Critic Or Follow-Up Failure

Critic/follow-up failure is a future turn workflow family, not part of source ingest or persona
setup.

Use `critic_failure` only when a required critic or follow-up provider step fails and the route
cannot safely complete. A domain critic report with `suggested_action=retry` or `log` is not
automatically an HTTP error.

If the primary assistant message is already durable and critic failure is non-fatal by accepted
policy, return success with a warning and link the critic/failure records. If critic is mandatory,
return `critic_failure` before business rows commit or `partial_persistence` after business rows
commit.

## Read-Only Inspection Expectations

Every implementation of a new write route must be debuggable through existing read-only routes:

| Inspection route | Required visibility | Redaction expectation |
| --- | --- | --- |
| `GET /workflow-runs/{workflow_id}` | Workflow type/status, persisted IDs, failed step, warnings, error details, and workflow links. | No raw source, prompts, provider payloads, trace payloads, paths, secrets, stack traces, memory content, or user text. |
| `GET /workflow-runs?request_id=...` | Find all workflows for a transport request. | Stable ordering and limit behavior from Batch 08. |
| `GET /workflow-runs?workflow_type=...` | Find runs by `source_work.ingest`, `character.create`, or `character_persona.setup`. | Same redaction as detail/list. |
| `GET /audit-events/{audit_event_id}` | Terminal audit event with operation, result, entity, actor attribution, related IDs, before/after if safe, and sanitized metadata. | Reason, before/after, and metadata recursively redacted by API redaction. |
| `GET /audit-events?workflow_id=...` | Find terminal audit events for one workflow. | Same redaction as detail/list. |
| `GET /llm-traces/{trace_id}` | Existing local trace inspection remains the route for trace debugging. | Write responses link trace IDs but do not inline trace payloads. |

The implementation batch may add read routes for new domain resources only when needed for API
usability. It must not bypass audit/workflow inspection by embedding raw diagnostics in write
responses.

## Candidate Matrix

| Candidate | Route | Type | Readiness | Required implementation boundary |
| --- | --- | --- | --- | --- |
| Source ingest | `POST /source-works` | Deterministic write using provider-ready foundations | Ready first | Add HTTP-safe application service accepting inline text, not local paths. Commit source work, chunks, workflow, links, audit, and idempotency together. |
| Character create | `POST /characters` | Deterministic write bridge | Ready after source ingest or in same focused batch if kept separate | Add application service with source lookup, duplicate-name conflict, audit, workflow, links, optional idempotency. |
| Persona setup | `POST /characters/{character_id}/persona-setup-runs` | Provider-backed staged workflow | Not first; ready after service hardening | Add staged application service, role-specific provider bundle, trace correlation, partial normalization, terminal replay for success/failure/partial. |

## Implementation Gating Checklist

Any provider-backed or provider-ready write route must satisfy this checklist before the route is
accepted:

- The route contract names the route, workflow type, audit operation, request model, response model,
  status codes, and error codes.
- The API handler is a thin adapter over `personality_jelly.application`; it does not call
  extraction, persona, provider, repository, or semantic modules directly except through accepted
  application services.
- `X-Request-ID` and body `request_id` are normalized and must match when both are present.
- Idempotency requirement is explicit. Provider-backed routes and source ingest require
  `Idempotency-Key`; deterministic bridge routes may make it optional only with a documented replay
  policy.
- Body/header `idempotency_key` matching is tested.
- The idempotency request hash excludes only `request_id`, `idempotency_key`, generated IDs, and
  timestamps; it includes path IDs and behavior-affecting body fields.
- Replay returns the original stored redacted payload and performs no provider calls or duplicate
  writes.
- Hash mismatch returns `409 conflict`; in-progress/crashed retry returns `409 retryable_conflict`
  when the route can detect it.
- Transaction boundaries are documented and tested, including rollback for validation/conflict and
  the exact point where partial persistence becomes possible.
- Persistent workflow runs are started, completed/failed/partialed, and linked to all input,
  created, updated, trace, audit, result, and idempotency records.
- Persistent audit events are stored in the accepted boundary, with compact before/after snapshots
  and sanitized metadata.
- Provider-backed routes persist safe trace IDs for each provider step when trace rows exist, with
  `request_id`, `workflow_id`, `workflow_step`, and related IDs.
- Success responses include every safe shared ID in `ids` and route-specific many-ID lists in
  `result.persisted_ids` and workflow links.
- Default responses and error envelopes pass the safe redaction profile and have route tests
  proving raw sensitive fields are absent.
- Provider failure, provider validation failure, partial persistence, retryable conflict, guard
  failure, and critic/follow-up failure shapes are covered where applicable.
- Existing `/workflow-runs` and `/audit-events` inspection routes can debug the created records.
- OpenAPI contract tests prove the default request/response schemas do not expose local paths,
  provider config, raw prompts, raw outputs, source text, memory content, or debug-only payloads.
- Focused application tests cover success, validation, not-found, conflict, replay, rollback,
  audit/workflow links, redaction, and provider/partial failures where applicable.
- Full test scope is chosen by blast radius. Shared helper or schema changes require broader tests
  than a route-only addition.

## Unresolved Implementation Decisions

These are not blockers for writing the next implementation plan, but they must be resolved in the
specific implementation task that touches them:

- Exact maximum inline source content size and chunking bounds.
- Whether `source_chunk_ids`, `canon_claim_ids`, `evidence_ref_ids`, and `claim_conflict_ids` are
  added to `WorkflowRelatedIds` or remain route-specific result fields plus workflow links.
- Whether oversized source content maps to `413 validation_error` or `422 validation_error` in the
  first implementation.
- Whether `POST /characters` is implemented in the same batch as source ingest or as a separate
  bridge task before persona setup.
- Exact provider role bundle schema supported at first setup implementation (`stub`, `env`,
  `named_config`, and role-level model aliases).
- Whether no-candidate Reader output is `422 validation_error` or `502 provider_validation_error`;
  no-verified-claims after verifier remains `partial_persistence` once business rows exist.
- Resume, cleanup, deduplication, and review policy for partially persisted persona setup attempts.
- Whether future local-debug read routes expose claim text, evidence excerpts, source chunks, or
  persona rules. The write response must not expose them by default.
