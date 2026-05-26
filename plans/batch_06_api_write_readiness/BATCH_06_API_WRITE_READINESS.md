# Batch 06 API Write Readiness

Batch 06 is a planning and readiness batch after the Batch 05 read-only FastAPI adapter closeout.
Its purpose is to convert deferred API concerns into safe implementation contracts before any HTTP
write workflow is exposed.

Follow `VIBE_CODING_GUIDE.md` as the source of truth. Batch 06 should not add write endpoints by
default. It should define boundaries, request/response expectations, error behavior, redaction
rules, pagination conventions, trace correlation, and acceptance criteria for later implementation
batches.

## Batch Goals

- Decide which existing application workflows are safe candidates for future HTTP write routes.
- Preserve explicit IDs for source works, characters, users, conversations, persona versions,
  memories, source chunks, traces, and eval records.
- Define transaction and partial-persistence behavior for future write workflows.
- Draw the actor/auth/audit boundary without introducing a full platform account system.
- Define API redaction policy for sensitive inspection surfaces before broad clients depend on
  them.
- Establish pagination and filter conventions beyond ad hoc `limit` handling.
- Plan request/workflow trace correlation so later write routes can be debugged end to end.
- Produce a closeout recommendation that names the next implementation batch and its non-goals.

## Non-Goals

- Do not add source ingest, character creation, conversation creation, turn execution, summary
  generation, benchmark execution, memory mutation, audit persistence, or other write routes.
- Do not add authentication, authorization, API keys, workspace membership, billing, quotas, CORS,
  deployment, server process management, or production UI.
- Do not add graph/vector databases, third-party memory systems, LangGraph, or provider-routing
  frameworks.
- Do not change semantic judgment behavior. Semantic decisions still require structured model
  outputs, embeddings, verified evidence, or human review.
- Do not move workflow logic into `personality_jelly.api`.

## Current Starting Point

Batch 05 has already introduced:

- `personality_jelly.api.create_app`;
- read-only `GET /health`;
- database/session dependencies;
- structured API error envelopes;
- read-only route families for conversation/context, character/claim/memory/source chunks,
  critic/failure/LLM trace, OOC eval runs, and retrieval eval runs.

The API remains an adapter over `personality_jelly.application`. Batch 06 planning should preserve
that structure and identify any application-service gaps that must be filled before future write
routes are implemented.

## Shared Guardrails

- Start each task from clean `dev` and use the scoped branch listed below.
- Development agents must not merge their task branch back into `dev` at completion. They should
  commit their task changes, push the task branch to `origin`, and report the branch and commit.
  A coordinator or maintainer handles review and integration into `dev`.
- Keep changes focused on the assigned planning artifact.
- Prefer explicit contracts over broad architecture essays.
- If a task finds an implementation blocker, document it as a prerequisite instead of fixing it in
  the planning branch.
- No automated tests are required for pure planning changes, but run `git diff --check` before
  pushing the task branch.

## Recommended Task Order

| Task | Branch | Can start | Depends on | Main output |
| --- | --- | --- | --- | --- |
| 01 Write Workflow Boundary Design | `planning/api-write-workflows` | Immediately | none | Future write route candidates, transaction policy, service prerequisites. |
| 02 Actor Auth Audit Boundary | `planning/api-actor-auth-audit` | Immediately | none | Local actor model, auth deferral line, audit event expectations. |
| 03 API Redaction Policy | `planning/api-redaction-policy` | After 01-02 context preferred | 01, 02 | Field-level redaction defaults for prompts, messages, memories, traces, and chunks. |
| 04 Pagination Filter Contract | `planning/api-pagination-filters` | Immediately | none | Shared list conventions, limits, cursor/readiness options, filter naming. |
| 05 Trace Workflow Correlation | `planning/api-trace-correlation` | After 01 context preferred | 01 | Request/workflow IDs, trace linking, migration options. |
| 06 Batch 06 Acceptance And Next Recommendation | `planning/batch-06-closeout` | After 01-05 | 01, 02, 03, 04, 05 | Acceptance summary and next implementation batch recommendation. |

Tasks 01, 02, and 04 can run in parallel. Tasks 03 and 05 can start once enough context exists but
should reconcile with Task 01 before completion. Task 06 should wait for all other planning tasks.

## Expected Outputs

Batch 06 should leave behind implementation-ready planning documents under this directory:

- `01_write_workflow_boundary_design.md`
- `02_actor_auth_audit_boundary.md`
- `03_api_redaction_policy.md`
- `04_pagination_filter_contract.md`
- `05_trace_workflow_correlation.md`
- `06_batch_06_acceptance_next_recommendation.md`

Each document should include:

- a concise current-state summary;
- future implementation contracts;
- explicit non-goals;
- service or schema prerequisites;
- validation expectations;
- open questions that should block implementation if unresolved.

## Acceptance For Batch 06

Batch 06 is complete when:

- all six planning tasks are merged by a coordinator into `dev`;
- the final closeout document identifies the recommended next batch;
- future write routes have explicit request, response, transaction, error, and audit expectations;
- redaction defaults are defined before sensitive fields are exposed to broad clients;
- pagination and filter conventions are documented for new and existing list endpoints;
- trace/workflow correlation has a migration-ready plan or a documented reason to defer schema
  changes;
- `VIBE_CODING_GUIDE.md` and `README.md` still match the actual project phase.

## Task 06 Closeout Recommendation

Task 06 accepts the Batch 06 planning outputs as implementation-ready contracts and recommends
**Batch 07 API Write Foundation** as the next batch.

The recommended first implementation scope is intentionally narrow:

- shared redaction profile and serializer foundation for new write-era responses;
- request/workflow correlation context and response fields;
- local actor context and payload-only audit boundary;
- deterministic application services and thin HTTP adapters for conversation creation;
- deterministic application services and thin HTTP adapters for manual memory review/edit/archive.

Provider-backed write workflows, source ingest, character/persona setup, turn execution, summary
generation, benchmark execution, persistent audit storage, auth/workspace/platform concerns, cursor
migrations, deployment, CORS, and UI remain deferred to later batches.

## Deferred To Later Batches

- Implementing write endpoints.
- Persisting audit events beyond the agreed readiness model.
- Production auth/workspace/platform integration.
- Server/deployment commands and CORS policy.
- UI integration.
