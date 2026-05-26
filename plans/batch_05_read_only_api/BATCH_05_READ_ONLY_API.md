# Batch 05 Read-Only API Adapter

Batch 05 is the first HTTP adapter batch. Its purpose is to introduce a thin FastAPI layer over the
existing `personality_jelly.application` services so local and future UI clients can inspect
persisted state without invoking write workflows.

Follow `VIBE_CODING_GUIDE.md` as the source of truth. Batch 05 may add FastAPI only for read-only
adapter work. It must not add write endpoints, auth/workspace/platform features, web UI work,
graph/vector databases, external memory frameworks, LangGraph, or new semantic behavior in HTTP
handlers.

## Batch Goals

- Add a small `personality_jelly.api` package.
- Introduce FastAPI as a runtime dependency only as needed for the adapter.
- Provide an app factory that can be tested without starting a network server.
- Reuse `personality_jelly.application` bootstrap and inspection services.
- Add database/session dependencies with explicit transaction behavior for read-only requests.
- Return one structured error envelope for lookup, validation, and unexpected errors.
- Expose only read-only inspection endpoints for existing persisted records.
- Keep CLI behavior unchanged.
- Preserve data-boundary IDs in every response: source work, character, user, conversation,
  persona version, context package, memory, evidence chunk, trace, and eval IDs where applicable.

## Non-Goals

- No source ingestion, character creation, conversation creation, turn execution, summary
  generation, benchmark execution, memory review/edit/archive, audit persistence, or other write
  operation through HTTP.
- No authentication, authorization, API keys, actor identity, workspace, billing, quotas, or
  deployment model.
- No production server entry point is required. A local app factory is enough for Batch 05.
- No OpenAPI polish beyond clear route names, tags, and stable response models.
- No local filesystem path access through HTTP.
- No semantic keyword, regex, fixed-vocabulary, or string-containment checks in API code.

## Proposed API Package Shape

Keep the API package adapter-only:

```text
src/personality_jelly/api/
  __init__.py
  app.py              # create_app(...)
  dependencies.py     # settings/database/session dependencies
  errors.py           # ErrorEnvelope and exception handlers
  schemas.py          # HTTP envelope/list models if needed
  routes/
    __init__.py
    health.py
    conversations.py
    characters.py
    diagnostics.py
```

Handlers should:

1. Validate HTTP path/query params.
2. Acquire a database session.
3. Call an application inspection service.
4. Return Pydantic models or a small HTTP envelope.
5. Map exceptions through the shared API error envelope.

Handlers should not:

- import CLI modules;
- construct prompts;
- call LLM providers;
- run semantic decisions;
- mutate storage state;
- perform ad hoc repository assembly when an application service already exists.

## Read-Only Endpoint Set

Batch 05 should expose these endpoint families, split by implementation task:

### Health And Metadata

- `GET /health`

The health endpoint should confirm process readiness and database migration readiness without
leaking local paths, secrets, or provider configuration.

### Conversation And Context

- `GET /conversations?limit=...`
- `GET /conversations/{conversation_id}`
- `GET /context-packages/{context_package_id}`

Use the existing conversation/context inspection services. Detail responses should preserve parsed
summary layers and linked IDs. Context package detail may expose `assembled_prompt` in this local
read-only phase because the CLI already exposes it; defer redaction and access policy to later
auth/workspace work.

### Character, Claim, Memory, And Source Chunk

- `GET /characters?source_work_id=...`
- `GET /characters/{character_id}`
- `GET /claims?character_id=...&status=...&claim_type=...`
- `GET /claims/{claim_id}`
- `GET /memories?user_id=...&character_id=...&scope=...&status=...`
- `GET /memories/{memory_id}`
- `GET /source-chunks/{chunk_id}`

Do not add global same-name character lookup. Do not mutate memory state. Preserve distinct
`memory_scope` and `memory_status` values. If a route needs a read-only list/discovery helper that
does not yet exist in `personality_jelly.application`, add the thin application service first and
keep repository assembly out of HTTP handlers.

### Critic, Failure, Trace, And Eval Diagnostics

- `GET /critic-reports/{critic_report_id}`
- `GET /failure-cases?conversation_id=...&category=...&limit=...`
- `GET /failure-cases/{failure_case_id}`
- `GET /llm-traces?operation=...&schema_name=...&provider_name=...&model_name=...&with_errors=...&limit=...`
- `GET /llm-traces/{trace_id}`
- `GET /eval-runs?character_id=...&test_suite=...&limit=...`
- `GET /eval-runs/{run_id}?failed_only=...`
- `GET /retrieval-eval-runs?character_id=...&source_work_id=...&test_suite=...&limit=...`
- `GET /retrieval-eval-runs/{run_id}?failed_only=...&include_chunks=...`

These routes should relay stored structured outputs from critic, trace, and benchmark services.
They must not reinterpret pass/fail or risk by matching strings.

## Error Envelope

Use one response shape for API errors:

```json
{
  "error": {
    "code": "not_found",
    "message": "Character not found: char_...",
    "details": {},
    "trace_id": null
  }
}
```

Minimum mappings:

- `LookupError` -> `404 not_found`
- Pydantic/FastAPI request validation -> `422 validation_error`
- `ValueError` from application services -> `422 validation_error`
- unexpected exceptions -> `500 unexpected_error`

Batch 05 should not introduce provider error mapping routes because no HTTP endpoint invokes
providers. Keep provider-specific codes documented for later write-workflow API batches.

## Dependency And Test Policy

- Add `fastapi` as a project dependency in the first implementation task.
- Add only the minimum test dependency needed for route tests. If route tests use FastAPI's
  `TestClient`, add the compatible client dependency explicitly when required by the installed
  FastAPI/Starlette versions.
- Do not add `uvicorn` unless a task explicitly needs a local server command. Batch 05 can be
  verified through app-factory tests.
- Tests should use in-memory SQLite or temporary database URLs and should not require network
  access or real providers.

## Shared Guardrails

- Start each task from clean `dev` and use the scoped branch listed below.
- Development agents must not merge their task branch back into `dev` at completion. They should
  commit their task changes, push the task branch to `origin`, and report the branch and commit.
  A coordinator or maintainer handles review and integration into `dev`.
- Keep changes small and focused on the assigned endpoint family or foundation concern.
- Preserve existing CLI behavior and application-service boundaries.
- Run focused tests for touched behavior before pushing the task branch.

## Recommended Task Order

| Task | Branch | Can start | Depends on | Main output |
| --- | --- | --- | --- | --- |
| 01 FastAPI App Foundation | `feature/api-app-foundation` | Immediately | none | Dependency update, `personality_jelly.api`, app factory, health route. |
| 02 Error And Session Dependencies | `feature/api-errors-sessions` | After 01 | 01 | Session dependency, request validation handling, structured error envelope. |
| 03 Conversation Context Routes | `feature/api-conversation-context` | After 02 | 02 | Conversation and context package read endpoints. |
| 04 Character Claim Memory Routes | `feature/api-character-memory` | After 02 | 02 | Character, claim, memory, and source chunk read endpoints. |
| 05 Diagnostic Eval Routes | `feature/api-diagnostic-eval-routes` | After 02 | 02 | Critic, failure, trace, OOC eval, and retrieval eval read endpoints. |
| 06 API Contract And Docs Pass | `feature/api-contract-docs` | After 03-05 | 03, 04, 05 | Route consistency pass, README/Vibe guide updates if needed, API test coverage gaps. |
| 07 Batch 05 Closeout Verification | `chore/batch-05-api-closeout` | After 06 | 01-06 | Full regression pass and final status snapshot. |

Tasks 03, 04, and 05 can run in parallel after Task 02 is merged because they touch mostly separate
route modules. Task 06 should wait for all route families so it can catch response-shape drift.

## Acceptance For Batch 05

Batch 05 is complete when:

- `personality_jelly.api.create_app` exists and can be tested without starting a server.
- `GET /health` works against a migrated test database.
- All planned read-only route families call application services rather than duplicating CLI logic.
- API errors use the structured envelope with stable `code`, `message`, `details`, and optional
  `trace_id`.
- Route tests cover success, not-found, validation-error, and filter behavior for each endpoint
  family.
- No HTTP endpoint writes domain state.
- CLI tests for existing list/show diagnostics still pass.
- The full pytest suite passes before closeout.

## Task 06 Contract Note

As of Task 06, Tasks 01-05 expose the planned Batch 05 endpoint families as GET-only routes. API
contract tests lock the route set, tags, query parameter names, and JSON response models. Route
handlers remain adapter-only: they acquire a session, call `personality_jelly.application`
inspection services, and rely on the shared error envelope.

No planned Batch 05 read-only endpoint family is intentionally deferred. Write workflows,
auth/platform concerns, deployment/server commands, and API-level redaction policy remain deferred
to later batches.

## Deferred To Later Batches

- Write workflows: ingest, character creation, conversation creation, turn execution, summary,
  benchmark execution, memory mutation, and audit persistence.
- Auth, actor identity, workspace, rate limiting, deployment, CORS policy, and production server
  commands.
- API-level redaction/access policy for assembled prompts, memories, raw messages, and LLM traces.
- Pagination beyond simple `limit` filters.
- Trace correlation schema changes and workflow run records.
