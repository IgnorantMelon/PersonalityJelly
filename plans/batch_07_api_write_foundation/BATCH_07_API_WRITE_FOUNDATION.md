# Batch 07 API Write Foundation

Batch 07 is the first implementation batch after Batch 06 API write readiness closeout. Its purpose
is to implement the smallest safe local write surface while preserving the adapter-only API
boundary.

Follow `VIBE_CODING_GUIDE.md` and the Batch 06 closeout contracts. Batch 07 may add HTTP write
routes only for the accepted deterministic local-first workflows. It must not expose
provider-backed workflows or platform-auth concerns.

## Batch Goals

- Add shared redaction profiles and serializers for new write-era API responses.
- Add request/workflow correlation context and response fields for write routes.
- Add local actor context and payload-only audit boundaries for application write services.
- Implement application services and thin HTTP adapters for conversation creation.
- Implement application services and thin HTTP adapters for manual memory review/edit/archive.
- Keep existing Batch 05 read-only route behavior compatible unless a task explicitly migrates a
  new response model.
- Keep write workflow logic in `personality_jelly.application`; FastAPI handlers remain adapters.

## Non-Goals

- Do not implement source ingest, character/persona setup, turn execution, summary generation,
  benchmark execution, or provider-backed write routes.
- Do not add persistent audit tables, audit repositories, workflow-run tables, LLM trace columns, or
  idempotency persistence unless a later task explicitly expands scope.
- Do not add production auth, accounts, API keys, workspace membership, roles, billing, rate
  limits, CORS, deployment, server process management, or UI.
- Do not add graph/vector databases, third-party memory systems, LangGraph, provider-routing
  frameworks, or external observability services.
- Do not change semantic judgment behavior, memory guard rules, benchmark pass/fail logic,
  retrieval behavior, or provider prompts.

## Starting Point

Batch 06 accepted these contracts:

- first write candidates are conversation creation and manual memory review/edit/archive;
- write handlers must stay thin over application services;
- default write-era responses should use safe redaction profiles;
- write responses should return request/workflow correlation IDs;
- local explicit actor context is required for attribution and payload-only audit;
- broad API/UI exposure still requires persistent audit and production auth decisions.

Relevant planning inputs:

- `plans/batch_06_api_write_readiness/01_write_workflow_boundary_design.md`
- `plans/batch_06_api_write_readiness/02_actor_auth_audit_boundary.md`
- `plans/batch_06_api_write_readiness/03_api_redaction_policy.md`
- `plans/batch_06_api_write_readiness/04_pagination_filter_contract.md`
- `plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`
- `plans/batch_06_api_write_readiness/06_batch_06_acceptance_next_recommendation.md`

## Shared Implementation Rules

- Start each task from clean `dev` and use the scoped branch listed below.
- Development agents must not merge their task branch back into `dev`; push the task branch for
  coordinator review.
- Add or update focused tests for any behavior change.
- Keep CLI behavior unchanged unless the task explicitly shares a new application service with CLI.
- Preserve stable Batch 05 read-only response behavior while adding safer write-era response shapes.
- Do not expose raw prompts, raw user text, full memories, full source chunks, full trace payloads,
  stack traces, local filesystem paths, secrets, auth headers, or API keys in default write
  responses.
- New write routes must return structured errors through the existing API error envelope or a
  documented extension of it.
- Application services should accept transport-neutral inputs and return Pydantic result models that
  can be used by API tests without starting a server.

## Recommended Task Order

| Task | Branch | Can start | Depends on | Main output |
| --- | --- | --- | --- | --- |
| 01 Redaction Profile Foundation | `feature/api-redaction-foundation` | Immediately | Batch 06 closeout | Shared redaction profile models/helpers and tests. |
| 02 Correlation Error Envelope Foundation | `feature/api-correlation-foundation` | Immediately | Batch 06 closeout | Request/workflow correlation context and response/error contract tests. |
| 03 Local Actor Audit Boundary | `feature/api-local-actor-audit` | After 01-02 context preferred | 01, 02 | Local actor context models and payload-only audit write-service boundary. |
| 04 Conversation Creation Write Route | `feature/api-conversation-create` | After 01-03 | 01, 02, 03 | Application service plus thin `POST /conversations` route. |
| 05 Manual Memory Write Routes | `feature/api-memory-mutations` | After 01-03 | 01, 02, 03 | Application services plus review/edit/archive memory routes. |
| 06 Batch 07 Closeout Verification | `chore/batch-07-write-foundation-closeout` | After 04-05 | 01, 02, 03, 04, 05 | Regression pass, API audit, docs/status update. |

Tasks 01 and 02 can run in parallel. Task 03 should reconcile the redaction/correlation result
models before defining actor/audit payloads. Tasks 04 and 05 can run in parallel after Tasks 01-03
are merged because they touch separate write workflow families.

## Expected Route Scope

The first Batch 07 write routes should be limited to deterministic local-first workflows:

- `POST /conversations`
- manual memory review route, exact path to be defined by Task 05;
- manual memory edit route, exact path to be defined by Task 05;
- manual memory archive route, exact path to be defined by Task 05.

Route names should follow existing Batch 05 conventions and remain explicit about IDs. If a route
path would conflict with future platform semantics, choose the narrower local route and document the
later migration path.

## Acceptance For Batch 07

Batch 07 is complete when:

- redaction profiles are implemented and tested for default write responses;
- request/workflow correlation IDs are present in write success responses and sanitized errors;
- local actor context is required for write services and validated before mutation;
- payload-only audit events are returned for accepted write workflows without adding audit storage;
- `POST /conversations` exists as a thin adapter over an application service;
- manual memory review/edit/archive write routes exist as thin adapters over application services;
- focused API/application tests cover success, validation, not-found, redaction, actor/reason, and
  correlation behavior;
- no provider-backed write route is exposed;
- full pytest passes before closeout if shared behavior is touched;
- `README.md` and `VIBE_CODING_GUIDE.md` match the implemented status.

## Closeout Verification

Batch 07 closeout verification passed after Tasks 01-05 were merged into `dev`.

Implemented write routes:

- `POST /conversations`
- `POST /memories/{memory_id}/review`
- `PATCH /memories/{memory_id}`
- `POST /memories/{memory_id}/archive`

Closeout validation:

- full pytest on merged `dev`: `279 passed, 3 warnings`;
- route audit confirmed the implemented write route set stays inside the accepted deterministic
  local-first scope;
- write handlers remain thin adapters over `personality_jelly.application`;
- default write responses apply redaction;
- request/workflow correlation IDs are returned for write workflows;
- manual memory mutations require local actor context and caller reason;
- payload-only audit metadata is returned where required;
- no provider-backed write route, persistent audit storage, auth/workspace feature, deployment,
  CORS, or UI was added.

Recommended next batch: **Batch 08 API Workflow Persistence Foundation**, focused on persistent
audit events, workflow-run/link persistence, idempotency/replay behavior, provider failure
contracts, and correlation/audit inspection needed before provider-backed write routes.

## Deferred To Later Batches

- Source ingest and file upload/http text ingestion.
- Character/persona setup, Reader/Verifier/persona compiler API workflows.
- Turn execution, summary generation, OOC benchmark execution, retrieval benchmark execution.
- Persistent audit event storage and audit list/detail routes.
- Workflow-run/link tables, LLM trace correlation columns, idempotency/replay persistence.
- Cursor migration for existing Batch 05 list endpoints.
- Production auth/workspace/platform features, deployment, CORS, and UI.
