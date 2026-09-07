# Batch 07 Closeout

Batch 07 API Write Foundation is closeout verified as a local-first deterministic write foundation.
It implements the accepted Batch 07 route scope without exposing provider-backed workflows or
platform-auth concerns.

## Acceptance Summary

Accepted Batch 07 outputs:

- redaction profile foundation for write-era responses;
- request/workflow correlation context and write response/error helpers;
- local actor context and payload-only audit boundary;
- conversation creation application service and `POST /conversations`;
- manual memory review/edit/archive application services and routes.

Implemented write routes:

- `POST /conversations`
- `POST /memories/{memory_id}/review`
- `PATCH /memories/{memory_id}`
- `POST /memories/{memory_id}/archive`

These routes are deterministic local-first workflows. They do not invoke providers, generate turns,
run summaries, ingest source text, execute benchmarks, or mutate source canon.

## Route Set Verified

The implemented route set remains inside the accepted Batch 07 scope:

- existing Batch 05 read-only routes remain present;
- `POST /conversations` is the only conversation write route;
- memory write routes are limited to manual review, edit, and archive;
- no source ingest, character/persona setup, turn execution, summary, benchmark, auth, deployment,
  CORS, or UI route was added.

The OpenAPI contract test was updated to lock the new write routes and existing read route set.

## Boundary Verification

Write route handlers remain thin adapters:

- they validate request bodies and headers;
- acquire a database session;
- call application services;
- return write-era response envelopes;
- map errors through the shared envelope.

Write workflow behavior lives in `personality_jelly.application`, not in HTTP handlers.

Redaction and exposure:

- write responses use the default local redaction profile;
- raw prompt-like fields, memory content/reasons, source text, provider payloads, secrets, local
  paths, and stack traces are not exposed by default;
- no local debug exposure mode was added through HTTP.

Correlation:

- write success responses include request/workflow IDs and workflow status;
- sanitized error details can carry correlation metadata;
- `trace_id` remains separate from request/workflow identity.

Actor and audit:

- deterministic write services require explicit local actor context;
- manual memory mutations require caller reasons;
- payload-only audit metadata is returned where required;
- no persistent audit table, repository, or migration was added.

## Tests Run

Closeout validation on merged `dev`:

```powershell
.\.venv\Scripts\python -m pytest
```

Result:

- `279 passed, 3 warnings`

Additional branch-level validation before merge:

- Task 01 redaction focused tests and API suite passed.
- Task 02 focused, API regression, and full suite passed.
- Task 03 focused actor/audit tests and full suite passed.
- Task 04 focused conversation creation tests and full suite passed.
- Task 05 focused memory mutation tests, affected suites, and full suite passed.

## Deferred Work

Deferred to later batches:

- source ingest write routes;
- character/persona setup routes;
- turn execution routes;
- summary generation routes;
- benchmark execution routes;
- persistent audit storage and audit inspection routes;
- workflow-run/link tables, LLM trace correlation columns, and durable idempotency/replay;
- cursor migration for existing Batch 05 list endpoints;
- production auth, workspace, platform roles, CORS, deployment, and UI.

## Recommended Next Batch

Recommended next batch: **Batch 08 API Workflow Persistence Foundation**.

Batch 08 should resolve the blockers that still prevent provider-backed write routes:

- persistent audit event schema/repository and transaction policy;
- workflow-run/link persistence for request/workflow/domain/trace correlation;
- idempotency and replay/conflict behavior for write retries;
- provider failure and partial-persistence error contracts;
- audit and correlation inspection surfaces if needed for debugging.

Batch 08 should not yet expose turn execution, character/persona setup, summaries, benchmarks, or
other provider-backed routes until durable audit/correlation/idempotency behavior is implemented and
tested.
