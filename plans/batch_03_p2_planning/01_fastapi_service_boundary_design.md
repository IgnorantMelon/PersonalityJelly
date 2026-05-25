# FastAPI Service Boundary Design

This is a P2 planning document for the first service/API boundary. It follows the current
CLI-first architecture described in `VIBE_CODING_GUIDE.md` and does not propose adding FastAPI or
implementation dependencies in this batch.

The design assumes the first API should wrap existing application behavior, not move business logic
into HTTP handlers. HTTP handlers should stay thin: validate request models, open a database
session, resolve configured providers, call a reusable service function, commit or roll back, and
serialize response models.

Note: `VIBE_CODING_GUIDE.md` references historical `docs/06_api_contracts.md`, but there is no
`docs/` directory in the current checkout. This plan is grounded in the currently implemented
modules and CLI surface.

## Boundary Shape

The first service phase should be organized around an application-service layer that both CLI and
future FastAPI handlers can call.

Suggested module ownership:

- `storage` continues to own persistence, ORM mapping, migrations, and repository lookup errors.
- `ingestion`, `characters`, `extraction`, `persona`, `runtime`, `critic`, `memory`, `retrieval`,
  and `evaluation` continue to own domain workflows and semantic model calls.
- A future `services` or `application` package should own request-shaped orchestration that is
  currently embedded in `src/personality_jelly/cli/main.py`: database/session setup, provider
  resolution, workflow sequencing, result shaping, and transaction boundaries.
- `cli` should format human-readable diagnostics only.
- Future `api` handlers should translate HTTP/Pydantic request and response models only.

The first API should expose persisted state and a small set of explicit workflows. It should not be
an HTTP mirror of every CLI command. Read-only inspection endpoints should come first because the
repositories and domain models already support them and because they make later write workflows
observable.

## Read-Only Inspection Surface

These endpoints can be designed before write workflows because they mostly wrap repositories and
summary helpers.

| Surface | Candidate operations | Current reusable code | Notes |
| --- | --- | --- | --- |
| Character inspection | list characters by `source_work_id`; get character by `character_id`; include latest persona summary and claim counts | `CharacterRepository`, `PersonaVersionRepository`, `CanonClaimRepository` | Avoid global same-name lookup; require IDs once multi-work support starts. |
| Conversation inspection | list recent conversations; get conversation with recent messages and parsed summary layers | `ConversationRepository`, `MessageRepository`, `parse_layered_summary` | Response should preserve `user_id`, `character_id`, `persona_version_id`, and `current_mode`. |
| Context package inspection | get context package by `context_package_id`; optionally expand claim, memory, and chunk IDs | `ContextPackageRepository`, repositories for linked entities | Default response can include `assembled_prompt`; later phases may redact or scope it. |
| Critic report inspection | get critic report by `critic_report_id`; list failure cases by conversation/category | `CriticReportRepository`, `FailureCaseRepository` | Keep risk fields and `suggested_action` structured, not text-only. |
| LLM trace inspection | list traces with filters; get trace by `trace_id` | `LLMRawOutputRepository` | Preserve validation errors, schema name, provider/model, and operation for debugging. |
| Benchmark run inspection | list/get OOC evaluation runs and retrieval evaluation runs; list case results; summarize reports | `EvaluationRunRepository`, `EvaluationCaseResultRepository`, `RetrievalEvaluationRunRepository`, `RetrievalEvaluationCaseResultRepository`, `summarize_ooc_benchmark`, `summarize_retrieval_benchmark` | Keep OOC and retrieval runs separate model families even if routed under one API namespace. |

Recommended read-only path families:

- `GET /characters?source_work_id=...`
- `GET /characters/{character_id}`
- `GET /conversations?user_id=...&character_id=...&limit=...`
- `GET /conversations/{conversation_id}`
- `GET /context-packages/{context_package_id}`
- `GET /critic-reports/{critic_report_id}`
- `GET /failure-cases?conversation_id=...&category=...&limit=...`
- `GET /llm-traces?...filters...`
- `GET /llm-traces/{trace_id}`
- `GET /eval-runs?...filters...`
- `GET /eval-runs/{run_id}`
- `GET /retrieval-eval-runs?...filters...`
- `GET /retrieval-eval-runs/{run_id}`

Read-only responses should be stable, structured equivalents of the current CLI `key=value`
diagnostics. They should not embed CLI formatting helpers as API logic.

## Write And Workflow Surface

These operations should be introduced after read-only inspection is available. Each should call a
service-level function that can also replace CLI orchestration.

| Workflow | Candidate service operation | Current reusable code | API readiness |
| --- | --- | --- | --- |
| Ingest source | `ingest_source_file` or `ingest_source_text` returning source work and chunks | `ingest_text_file` | Needs API-safe input story. File paths are CLI-local; HTTP should use upload or text payload. |
| Create character | create character under an existing source work | `create_character` | Ready once request validation rejects blank names/aliases and requires `source_work_id`. |
| Start conversation | create or reuse user, select character and persona version, create conversation | `create_user`, `create_conversation`, repositories | Needs service policy for user identity and persona selection. API should not silently create demo users by default. |
| Run turn | append user message, build context, generate assistant response, optional critic, optional memory curation, optional retry | `send_roleplay_turn`, `send_message`, `build_context_package`, `evaluate_message`, `curate_memories_for_message` | Most important first write API, but requires provider resolution, transaction, timeout, and error contracts. |
| Run benchmark | run OOC or retrieval benchmark and persist results | `run_ooc_benchmark`, `run_retrieval_benchmark` | Should likely be admin/dev-only in the first service phase. Consider synchronous only for local MVP, with later job model. |

The CLI `demo` command should not become one public endpoint. It is a convenience script that
combines source ingestion, character creation, extraction, verification, persona compilation, user
creation, conversation creation, and a turn. Those underlying steps can become service operations,
but the one-shot demo workflow should stay CLI-only or be exposed later as an explicitly marked
development endpoint.

Suggested workflow path families:

- `POST /sources`
- `POST /characters`
- `POST /conversations`
- `POST /conversations/{conversation_id}/turns`
- `POST /eval-runs`
- `POST /retrieval-eval-runs`

Manual memory review/edit/archive commands are intentionally outside this task's requested mapping.
They should wait for the user/workspace/audit model plan because write permissions and audit trails
matter more there than for local CLI use.

## Request Model Families

Request models should be separate from domain models. Domain models represent persisted state;
request models represent allowed API intent.

Candidate request families:

- `SourceIngestRequest`: upload/text metadata, `title`, optional `author`, `language`,
  `source_type`. Avoid local filesystem paths in HTTP contracts.
- `CharacterCreateRequest`: `source_work_id`, `canonical_name`, `aliases`.
- `ConversationCreateRequest`: `user_id` or controlled user creation fields, `character_id`,
  optional `persona_version_id`, optional initial `interaction_mode`.
- `TurnRunRequest`: `content`, optional `interaction_mode`, `retry_on_critic`, provider selection
  policy if allowed, and optional booleans for critic/memory/retrieval participation.
- `OOCBenchmarkRunRequest`: `character_id`, optional `persona_version_id`, `test_suite`, optional
  explicit cases, provider policy.
- `RetrievalBenchmarkRunRequest`: `character_id`, optional `test_suite`, optional explicit cases,
  `max_cases`, `include_empty_case`, embedding provider policy.
- List filter models: pagination/limit plus supported filters such as `character_id`,
  `source_work_id`, `conversation_id`, `operation`, `schema_name`, `provider_name`, `model_name`,
  `with_errors`, and `test_suite`.

Request validation should reject ambiguous cross-entity combinations early. Examples: a provided
`persona_version_id` must belong to `character_id`; a conversation turn should not allow changing
`character_id`; benchmark cases files should use the existing Pydantic validation rules rather than
HTTP-specific ad hoc parsing.

## Response Model Families

Response models can wrap current domain models but should avoid leaking persistence implementation
details.

Candidate response families:

- Entity summaries: `SourceWorkSummary`, `CharacterSummary`, `PersonaVersionSummary`,
  `ConversationSummary`, `MessageSummary`, `MemorySummary`, `ClaimSummary`, `SourceChunkSummary`.
- Entity details: full `CharacterDetail`, `ConversationDetail`, `ContextPackageDetail`,
  `CriticReportDetail`, `LLMTraceDetail`, `BenchmarkRunDetail`, `RetrievalBenchmarkRunDetail`.
- Workflow results: `SourceIngestResult`, `CharacterCreateResult`, `ConversationCreateResult`,
  `TurnRunResult`, `BenchmarkRunResult`, `RetrievalBenchmarkRunResult`.
- Diagnostics: `OOCBenchmarkReport`, `RetrievalBenchmarkReport`, `LayeredSummary`, and
  `RetrievalCaseDiagnostics`.
- Link expansion pattern: default responses preserve IDs; optional expansion can include linked
  summaries where cheap and unambiguous.

Turn responses should include at minimum:

- `conversation_id`
- `user_message`
- `assistant_message`
- `context_package_id`
- `interaction_mode`
- `critic_report_id` and critic summary when present
- created memory IDs and statuses
- retry count and rejected message/report IDs when a retry occurred
- failure case IDs

This mirrors `RoleplayTurnOrchestrationResult` without making HTTP handlers understand runtime
internals.

## Error Model Expectations

Use one structured error envelope across API handlers:

- `error.code`: stable machine-readable code.
- `error.message`: short user-facing message.
- `error.details`: optional structured diagnostics.
- `error.trace_id`: optional API request ID or linked LLM trace ID when relevant.

Expected mappings:

- Missing IDs: repository `LookupError` maps to `404 not_found` with `entity_type` and `id`.
- Validation failures: Pydantic validation errors and domain `ValueError` from bad request shape map
  to `422 validation_error`; include field-level details when available.
- Cross-entity validation failures: mismatched persona/character, user/character, source/character,
  or run/result relationships map to `409 relationship_conflict` or `422 validation_error`
  depending on whether the payload is syntactically valid but inconsistent with stored state.
- Provider configuration failures: missing model/API configuration maps to `503 provider_unavailable`
  or `424 provider_dependency_failed`; include provider role such as `roleplay`, `critic`,
  `memory_curator`, `mode_classifier`, or `retriever`.
- Provider runtime failures: network, timeout, provider schema mode failure, or embedding failure
  maps to `502 provider_error` or `504 provider_timeout`; preserve any recorded LLM trace ID.
- Structured output validation failures: invalid provider JSON maps to `502 provider_validation_error`
  and should link to the persisted `LLMRawOutput` when recorded.
- Guard/critic failures: when Critic suggests retry/log, the turn itself can still be a successful
  `200` workflow result with `critic.suggested_action`, `failure_case_ids`, and `retry_count`.
  Exceptions inside critic or memory guard provider calls should use provider error codes. Guard
  unavailable memories should stay `candidate`, consistent with the current runtime rule.

Do not infer semantic pass/fail through keyword rules in the API layer. API code should only relay
structured critic, guard, benchmark, and retrieval outputs produced by existing modules.

## CLI Workflow Mapping

Natural API/service operations:

- Character inspection: read-only endpoint and shared inspection service.
- Conversation inspection: read-only endpoint and shared inspection service.
- Context package inspection: read-only endpoint and shared inspection service.
- Critic report inspection: read-only endpoint and shared inspection service.
- LLM trace inspection: read-only endpoint and shared inspection service.
- Benchmark run inspection: read-only endpoint and shared inspection service for OOC and retrieval
  runs.
- Ingest source: write workflow, but convert from filesystem path to upload/text API contract.
- Create character: write workflow under an explicit `source_work_id`.
- Start conversation: write workflow requiring explicit user and character identity.
- Run turn: write workflow backed by `send_roleplay_turn`.
- Run benchmark: write workflow backed by `run_ooc_benchmark` or `run_retrieval_benchmark`.

Should stay CLI-only in the first service phase:

- `demo`: a local convenience pipeline, not a stable product workflow.
- `db status` and `db migrate`: operational CLI commands, not public API endpoints.
- `config show` and `config check`: local diagnostics; exposing them requires an admin/security
  model first.
- Cases-file import/export paths: keep as CLI filesystem workflows initially. API can accept
  structured cases in request bodies after service models exist.
- Manual memory review/edit/archive: defer until user/workspace/audit ownership is designed.
- Any endpoint that accepts arbitrary local file paths from a remote caller.

## Refactor Prerequisites

Before API implementation starts, extract shared services from CLI-only orchestration:

1. Session/provider bootstrap

   `src/personality_jelly/cli/main.py` currently resolves database URL, creates engines/sessions,
   ensures migrations, and builds stub/env providers. A service boundary needs reusable factories
   that CLI and API can both call without importing CLI helpers.

2. Inspection services

   The CLI currently combines repository reads with `print` formatting for conversations, context
   packages, critic reports, characters, traces, failures, and eval runs. Create structured
   inspection functions that return response-shaped dataclasses/Pydantic models; keep printing in
   CLI.

3. Demo workflow decomposition

   `_prepare_demo_persona`, `_resolve_demo_user`, and `_resolve_demo_conversation` encode useful
   orchestration but are demo-specific and use `reuse_existing` semantics. Split reusable
   operations for ingest, character create, extraction/verification/persona compile, user create,
   and conversation create before offering API writes.

4. Provider role configuration

   `send_roleplay_turn` already distinguishes roleplay, critic, memory curator, mode classifier,
   and retriever providers. API services need a consistent policy for which roles are enabled, how
   model configs are selected, and how provider failures are reported.

5. Transaction boundaries

   CLI commands generally commit after a workflow. API services should make transaction ownership
   explicit per operation. Long workflows such as turn generation and benchmarks should define what
   is persisted when a later provider call fails.

6. Pagination and filtering

   Several repositories expose `list_recent(limit=...)`, but API list endpoints need stable limit
   defaults, maximums, and eventually cursor/page support. This can start simple, but it should not
   be buried in handlers.

7. Missing historical contract

   If `docs/06_api_contracts.md` is restored later, compare it against this plan before
   implementation. Do not silently implement a stale contract that conflicts with current domain
   boundaries.

## Non-Goals For The First Service Phase

- Do not add FastAPI, ASGI server configuration, OpenAPI generation, or dependency changes in this
  planning batch.
- Do not implement authentication, authorization, multi-tenant workspace isolation, billing,
  quotas, or public deployment concerns.
- Do not add a production web UI.
- Do not expose database migration or local configuration secrets through public endpoints.
- Do not convert the one-shot `demo` command into a product API.
- Do not accept local filesystem paths through remote API requests.
- Do not add multi-work or multi-character schema changes in this task.
- Do not introduce graph/vector databases, LangGraph, third-party memory systems, or external eval
  frameworks.
- Do not move semantic judgment into API handlers or add keyword/regex semantic checks.
- Do not make benchmark execution asynchronous until a job model and observability contract are
  designed.
