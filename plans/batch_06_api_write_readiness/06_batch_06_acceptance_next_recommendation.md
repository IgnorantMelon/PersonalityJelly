# Batch 06 Acceptance And Next Recommendation

Batch 06 is accepted as an implementation-readiness planning batch. It does not implement HTTP
write routes, but it converts the deferred API concerns from Batch 05 into contracts that a later
implementation batch can follow without moving workflow logic into `personality_jelly.api`.

## Current State

Batch 05 already closeout-verified the read-only FastAPI adapter over
`personality_jelly.application`. Batch 06 now adds planning outputs for:

- future write workflow boundaries;
- local actor/auth/audit boundaries;
- API redaction and exposure defaults;
- pagination, ordering, and filter conventions;
- request/workflow/LLM-trace correlation.

All five prerequisite planning outputs are present under `plans/batch_06_api_write_readiness/`.
Tasks 01-05 were merged into `dev` before this closeout branch was created.

## Acceptance Summary

| Batch 06 goal | Accepted output | Acceptance result |
| --- | --- | --- |
| Decide safe future write route candidates | `01_write_workflow_boundary_design.md` | Accepted with a narrow first candidate set: conversation creation and manual memory review/edit/archive. |
| Preserve explicit IDs and write contracts | `01_write_workflow_boundary_design.md`, `05_trace_workflow_correlation.md` | Accepted. Future responses should keep source, character, user, conversation, persona, memory, trace, eval, and workflow IDs explicit. |
| Define transaction and partial-persistence behavior | `01_write_workflow_boundary_design.md` | Accepted. Deterministic writes are single-transaction; provider-backed writes remain blocked until correlation and partial persistence are hardened. |
| Draw actor/auth/audit boundary | `02_actor_auth_audit_boundary.md` | Accepted. Use explicit local actor context now; defer production auth/workspace/account semantics. |
| Define redaction policy | `03_api_redaction_policy.md` | Accepted. New write-era defaults should use safe redaction profiles and keep debug exposure explicit. |
| Establish pagination/filter conventions | `04_pagination_filter_contract.md` | Accepted. Future lists use shared limits, exact-match filters, stable ordering, and cursor-ready envelopes. |
| Plan trace/workflow correlation | `05_trace_workflow_correlation.md` | Accepted. Use response-only correlation for deterministic writes first, then add workflow/trace persistence before provider-backed writes. |
| Recommend next implementation batch | This closeout document | Accepted as Batch 07 API Write Foundation. |

## Accepted Contracts

### Write Workflow Candidates

The first implementation batch should not expose the full deferred write surface. The accepted first
write candidates are:

- conversation creation;
- manual memory review;
- manual memory edit;
- manual memory archive.

These candidates are safe first because they are deterministic, can be scoped to existing domain
IDs, do not invoke providers, and can be implemented as thin HTTP adapters over explicit
application services.

The following workflows require more application-service hardening before HTTP exposure:

- source ingest;
- character creation and persona setup;
- turn execution;
- summary generation;
- OOC benchmark execution;
- retrieval benchmark execution;
- persistent audit writes.

Provider-backed workflows are blocked until request/workflow correlation, trace linking, partial
persistence, retry behavior, and redaction defaults are implemented and tested.

### Actor, Auth, And Audit

Future write services should accept a local actor context that is explicit and transport-neutral.
The actor context is for attribution and audit, not authentication.

The accepted local boundary is:

- require an explicit actor identity for write workflows;
- keep `user_id` as the memory/conversation continuity subject, not a login account;
- require caller reasons for manual semantic-state changes such as memory review/edit/archive;
- return payload-only audit events for narrow local-first routes when persistent audit does not yet
  exist;
- require append-only persistent audit before broad API/UI exposure or semantic governance writes.

Deferred concerns remain out of scope:

- login, sessions, OAuth, accounts, API keys;
- workspace membership, roles, tenant isolation;
- billing, quotas, rate limits;
- production compliance/export tooling.

### Redaction Defaults

New write-era API responses should not inherit the broad raw inspection exposure from the local
Batch 05 read-only adapter.

Accepted redaction profiles:

- `local_default`: default for new local clients; expose IDs, statuses, counts, timestamps, risk
  labels, and compact previews while redacting raw prompts, raw user text, full memories, full source
  chunks, full trace payloads, and stack traces.
- `local_debug`: explicit local diagnostic mode; may expose targeted raw debugging fields, but never
  secrets, auth headers, API keys, raw provider config, or local filesystem paths.
- `platform_default`: future broad-client baseline; redact raw text and diagnostic payloads until
  ownership/auth policy exists.

Redaction should live in a shared application-level serialization layer used by API response
models. Repositories should keep raw persisted values, and HTTP handlers should select a profile
rather than implementing field-by-field redaction.

### Pagination And Filters

Accepted list conventions for later implementation batches:

- default `limit=50`;
- maximum `limit=200`;
- minimum `limit=1`;
- no offset pagination;
- prepare cursor-based keyset pagination for new or migrated list endpoints;
- use exact-match `snake_case` filters and `_id` suffixes for identity filters;
- treat `include_*` parameters as expansions, not filters;
- enforce stable ordering with deterministic tie-breakers before adding cursors.

Existing Batch 05 list behavior should remain compatible until a coordinated migration updates
tests and clients.

### Trace And Workflow Correlation

Accepted correlation model:

- `request_id` identifies one HTTP request;
- `workflow_id` identifies one application workflow invocation;
- `llm_trace_id` identifies one stored LLM trace and must not be overloaded as request/workflow
  identity;
- domain object IDs remain explicit in responses and audit metadata.

For the first deterministic write routes, response-only `request_id` and `workflow_id` are enough.
Before provider-backed HTTP writes, add durable workflow and trace linkage through either nullable
trace columns, workflow run/link tables, or the recommended hybrid approach.

Error envelopes should eventually expose request/workflow correlation explicitly. Until the error
schema is migrated, correlation can be placed under `details.correlation`.

## Conflict And Gap Resolution

Tasks 01-05 are mostly aligned. The closeout resolves the main sequencing question by splitting
implementation into deterministic local-first writes before provider-backed writes.

Resolved decisions:

- Conversation creation and manual memory mutation are the first write candidates.
- Redaction and correlation foundations should land before or alongside those first routes.
- Payload-only audit is acceptable for narrow local-first deterministic routes, but persistent audit
  is required before broad API/UI exposure.
- Existing Batch 05 read-only routes should not be broken by the redaction or pagination contracts;
  new write-era routes should start with safer defaults.

Open blockers for later batches:

- persistent audit schema, repository, and transaction semantics;
- idempotency/replay semantics for client retries;
- durable workflow run/link schema for provider-backed routes;
- `llm_raw_outputs` correlation fields or an equivalent link table;
- deterministic ordering and repository-level limit support for migrated list endpoints;
- application services for conversation creation and manual memory review/edit/archive;
- redaction serializer/profile implementation and route tests;
- production auth/workspace/ownership policy.

## Recommended Next Batch

Recommended next batch: **Batch 07 API Write Foundation**.

Batch 07 should implement the smallest safe write foundation for local usage. It should avoid
provider-backed workflows and broad platform concerns.

Recommended Batch 07 scope:

- shared redaction profile and serializer foundation for new write-era responses;
- request/workflow correlation context and response fields for write routes;
- local actor context models accepted by application write services;
- application services for conversation creation and manual memory review/edit/archive;
- thin FastAPI write adapters for those deterministic workflows;
- payload-only audit events returned by the services and redacted by default;
- route and service tests for success, validation, not-found, redaction, actor context, and
  correlation behavior.

Recommended Batch 07 non-goals:

- source ingest write route;
- character/persona setup write route;
- turn execution write route;
- summary generation route;
- benchmark execution routes;
- persistent audit table or repository;
- auth, API keys, accounts, workspaces, roles, CORS, deployment, UI;
- cursor migration for existing Batch 05 list endpoints;
- provider-backed workflow correlation persistence.

## Recommended Batch 07 Task Order

1. Redaction profile foundation
   - Add shared redaction profile models/helpers for write-era responses.
   - Add unit tests proving secrets, local paths, raw prompts, raw user text, full memories, source
     text, trace payloads, and stack traces are excluded from default responses.
2. Correlation and error-envelope foundation
   - Add request/workflow correlation models in `application`.
   - Define how API handlers normalize `X-Request-ID` or body request IDs.
   - Return request/workflow IDs in success responses and sanitized error details.
3. Local actor context and payload-only audit service boundary
   - Add transport-neutral local actor context models.
   - Ensure manual memory operations require actor and reason.
   - Keep persistent audit deferred.
4. Conversation creation application service and route
   - Implement deterministic service wrapper over existing repositories.
   - Add a thin FastAPI adapter and route tests.
5. Manual memory review/edit/archive services and routes
   - Implement deterministic service wrappers that return updated memory summaries and audit
     payloads.
   - Add route tests for actor/reason validation, redaction, and not-found behavior.
6. Batch 07 closeout verification
   - Run focused API/application tests.
   - Run full pytest if shared behavior is touched.
   - Update README/VIBE only after the implementation status changes.

## Validation Expectations

Before implementing any Batch 07 route:

- route handlers must remain adapter-only;
- write behavior must live in `personality_jelly.application` or domain services;
- raw persisted data must not be removed or rewritten just to satisfy redaction;
- redaction tests must cover recursive sensitive keys and representative response surfaces;
- actor context and request/workflow correlation must be present in write response contracts;
- deterministic write services must rollback on validation or missing-ID failures.

Before implementing provider-backed write routes:

- durable workflow-run correlation or equivalent trace linkage must exist;
- provider failure and validation errors must be normalized;
- partial persistence and retry semantics must be explicit;
- persistent audit expectations must be resolved;
- redaction defaults must be applied to traces, prompts, critic reports, failures, and benchmark
  outputs.

## Explicit Non-Goals For This Closeout

- No HTTP write endpoints are implemented.
- No source code, migrations, dependencies, tests, auth, CORS, deployment, UI, or provider behavior
  are changed.
- Earlier Batch 06 task outputs are not rewritten.
- This document does not merge the closeout branch back to `dev`; coordinator review still applies.
