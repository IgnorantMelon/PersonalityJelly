# Batch 08 API Workflow Persistence Foundation

Batch 08 is the implementation batch after Batch 07 API Write Foundation. Its purpose is to add
the durable workflow, audit, and retry foundations required before provider-backed HTTP write
routes can be safely exposed.

Follow `VIBE_CODING_GUIDE.md`, the Batch 07 closeout, and the accepted Batch 06 write-readiness
contracts. Batch 08 may add persistence, application services, deterministic write-route wiring,
and read-only inspection for audit/correlation debugging. It must not expose provider-backed write
workflows.

## Batch Goals

- Persist append-only audit events for existing deterministic write workflows.
- Persist workflow runs and workflow links for request/workflow/domain/trace correlation.
- Add durable idempotency/replay support for deterministic write retries and future provider
  workflows.
- Define provider failure and partial-persistence contracts without adding provider-backed routes.
- Add redaction-aware read-only inspection surfaces for audit events and workflow runs.
- Keep API handlers thin over `personality_jelly.application`.

## Non-Goals

- Do not add source ingest, character/persona setup, turn execution, summary generation, benchmark
  execution, or other provider-backed write routes.
- Do not add auth, accounts, API keys, workspace membership, roles, billing, rate limits, CORS,
  deployment, server process management, or UI.
- Do not add graph/vector databases, third-party memory systems, external observability services,
  LangGraph, or provider-routing frameworks.
- Do not change semantic judgment behavior, prompts, memory guard rules, benchmark pass/fail logic,
  retrieval behavior, or provider selection.
- Do not migrate existing Batch 05 read-only list routes to cursor pagination in this batch.

## Starting Point

Batch 07 implemented:

- redaction profile and serializer foundations for write-era responses;
- request/workflow correlation context and response fields;
- local actor context and payload-only audit boundaries;
- `POST /conversations`;
- manual memory review/edit/archive write routes.

Batch 07 deliberately did not add persistent audit storage, workflow-run tables, LLM trace
correlation columns, or durable idempotency/replay.

Relevant planning inputs:

- `plans/batch_06_api_write_readiness/01_write_workflow_boundary_design.md`
- `plans/batch_06_api_write_readiness/02_actor_auth_audit_boundary.md`
- `plans/batch_06_api_write_readiness/03_api_redaction_policy.md`
- `plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`
- `plans/batch_07_api_write_foundation/BATCH_07_CLOSEOUT.md`

## Shared Implementation Rules

- Use the dependency-branch workflow in `VIBE_CODING_GUIDE.md`.
- Tasks 01 and 02 are independent enough to start from clean `dev` and run in parallel.
- Task 03 starts from the completed Task 02 branch; it does not need to wait for Task 02 to merge
  into `dev`.
- Task 04 starts from a dependency integration branch that combines Tasks 01 and 03.
- Task 05 starts from a dependency integration branch that combines Tasks 01 and 02.
- Coordinator integration still merges accepted branches into `dev` in dependency order and reruns
  the required validation on `dev`.
- If concurrent migration versions conflict, resolve ordering in the dependency integration or
  coordinator merge branch. Keep migration functions idempotent with `checkfirst=True` where
  practical.
- Add or update focused tests for every behavior change. Run the full suite before closeout and
  before submitting any branch that touches shared storage or API behavior broadly.
- Existing Batch 07 write responses should remain compatible except for additive audit/workflow and
  idempotency fields.
- Redaction defaults must continue to exclude raw prompts, raw provider payloads, full source text,
  full memory content, secrets, local paths, and stack traces.

## Recommended Task Order

| Task | Branch | Branch base | Depends on | Main output |
| --- | --- | --- | --- | --- |
| 01 Persistent Audit Event Storage | `feature/api-persistent-audit-events` | clean `dev` | Batch 07 closeout | `audit_events` schema/repository/service wiring and deterministic write audit persistence. |
| 02 Workflow Run And Link Persistence | `feature/api-workflow-run-persistence` | clean `dev` | Batch 07 closeout | `workflow_runs`, `workflow_run_links`, LLM trace correlation fields, and workflow persistence helpers. |
| 03 Idempotency Replay Foundation | `feature/api-idempotency-replay` | completed Task 02 branch | 02 | Durable idempotency records and replay/conflict behavior for deterministic write routes. |
| 04 Provider Failure Partial-Persistence Contracts | `feature/api-provider-failure-contracts` | integration of 01 and 03 | 01, 02, 03 | Normalized provider failure, partial result, retry hint, and persisted-ID contracts. |
| 05 Audit Correlation Inspection Routes | `feature/api-audit-workflow-inspection` | integration of 01 and 02 | 01, 02 | Read-only audit/workflow inspection services and routes. |
| 06 Batch 08 Closeout Verification | `chore/batch-08-workflow-persistence-closeout` | clean `dev` after 01-05 merge | 01-05 | Regression pass, route/storage audit, docs/status update, and next-batch recommendation. |

Tasks 01 and 02 can run in parallel. Task 05 can start after Tasks 01 and 02 are complete, while
Task 03/04 continue. Task 04 should use an integration branch because it needs both persistent audit
and idempotency/workflow context.

## Expected Route Scope

Batch 08 should preserve the existing write route set:

- `POST /conversations`
- `POST /memories/{memory_id}/review`
- `PATCH /memories/{memory_id}`
- `POST /memories/{memory_id}/archive`

Batch 08 may add read-only local inspection routes for debugging durable workflow foundations:

- `GET /audit-events`
- `GET /audit-events/{audit_event_id}`
- `GET /workflow-runs`
- `GET /workflow-runs/{workflow_id}`

Exact route naming should follow existing API route conventions and remain redaction-aware. Do not
add write routes for provider-backed workflows in this batch.

## Acceptance For Batch 08

Batch 08 is complete when:

- existing deterministic write workflows persist required audit events in the same transaction as
  the domain mutation;
- workflow runs and workflow links are persisted for existing deterministic write workflows;
- LLM trace correlation fields or links exist for future provider-backed diagnostics;
- deterministic write retries can use durable idempotency records for replay or conflict detection;
- provider failure and partial-persistence errors have normalized, redacted application/API
  contracts;
- audit and workflow inspection routes expose safe local diagnostics with focused filters;
- existing Batch 05 read-only routes and Batch 07 deterministic write routes remain compatible;
- no provider-backed write route, auth/workspace feature, deployment, CORS, UI, or new semantic
  behavior is added;
- focused storage/application/API tests pass;
- full pytest passes before closeout;
- `README.md`, `VIBE_CODING_GUIDE.md`, and this batch plan match the implemented status.

## Closeout Verification

Closeout should verify:

- schema migrations apply cleanly to a fresh database and an existing migrated database;
- audit rows are append-only and redacted before HTTP exposure;
- workflow run/link rows capture request ID, workflow ID, workflow type, status, related IDs, and
  linked domain/audit IDs;
- idempotency replay returns the stored result without duplicating domain/audit/workflow rows;
- idempotency conflicts return `409 conflict` with sanitized details;
- provider failure and partial-persistence contracts do not leak prompts, raw provider payloads,
  secrets, local paths, or stack traces;
- route handlers remain adapters over application services;
- full pytest passes on merged `dev`.

## Closeout Status

Batch 08 is closeout verified on merged `dev` as of 2026-05-27.

- Integrated order: Task 01 persistent audit events, Task 02 workflow run/link persistence, Task 03
  idempotency replay, Task 04 provider failure/partial-persistence contracts, Task 05 audit/workflow
  inspection routes.
- Schema verified: `audit_events`, `workflow_runs`, `workflow_run_links`, `idempotency_records`,
  and LLM trace correlation fields (`request_id`, `workflow_id`, `workflow_step`, `related_ids`).
- Route scope verified: existing deterministic write routes remain limited to `POST /conversations`,
  `POST /memories/{memory_id}/review`, `PATCH /memories/{memory_id}`, and
  `POST /memories/{memory_id}/archive`; Batch 08 only added read-only `GET /audit-events`,
  `GET /audit-events/{audit_event_id}`, `GET /workflow-runs`, and
  `GET /workflow-runs/{workflow_id}` inspection routes.
- Validation on merged `dev`: focused Batch 08 tests passed (`90 passed, 15 warnings`) and full
  pytest passed (`317 passed, 15 warnings`).
- Closeout artifact: `plans/batch_08_api_workflow_persistence/BATCH_08_CLOSEOUT.md`.
