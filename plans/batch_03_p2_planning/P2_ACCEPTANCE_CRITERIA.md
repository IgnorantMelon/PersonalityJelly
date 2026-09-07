# P2 Acceptance Criteria Snapshot

This document closes Batch 03 planning. It consolidates the accepted outputs from Tasks 01-05 and
defines concrete P2 acceptance criteria plus the recommended first implementation batch.

P2 should move Personality Jelly from a CLI-only MVP toward a reusable service foundation while
preserving the current canon, memory, critic, trace, and benchmark boundaries. It should not turn
the project into a platform, production API, graph system, or web UI in one step.

## Accepted P2 Direction

The accepted direction is service-first:

- Extract thin application services from CLI orchestration before adding HTTP handlers.
- Keep existing domain modules as behavior owners: ingestion, characters, extraction, persona,
  retrieval, runtime, critic, memory, evaluation, storage, and llm.
- Keep CLI output stable and script-friendly while it starts consuming structured service results.
- Treat a future FastAPI layer as an adapter over application services, not as the place where
  workflow or semantic logic lives.
- Preserve current semantic judgment rules: no keyword, regex, fixed-vocabulary, or
  string-containment judges for interaction mode, memory safety, critic review, benchmark pass/fail,
  retrieval quality, canon safety, or user/relationship interpretation.

## Accepted Service Boundary

Task 01 established that the first service/API boundary should wrap existing behavior through a
small application-service layer:

- Read-only inspection services should come first because they reuse existing repositories and make
  later writes debuggable.
- Write workflows should follow once bootstrap, provider resolution, transaction ownership, and
  error contracts are explicit.
- HTTP handlers, when added later, should validate transport request models, open sessions, resolve
  providers, call application services, and serialize responses.
- API request models should be separate from persisted domain models.
- API error responses should use one structured envelope with stable code, message, details, and
  optional trace/request IDs.

P2 implementation should expose or prepare these service surfaces:

- Character, conversation, context package, critic report, failure case, trace, OOC eval run, and
  retrieval eval run inspection.
- Source ingest, character create, conversation create, turn run, summary, and benchmark run
  workflows after inspection services are stable.
- Turn result shaping that includes message IDs, context package ID, critic/failure IDs, retry
  details, and created memory IDs.

## Data-Boundary Risks And Prerequisites

Task 02 found that core IDs are mostly preserved, but MVP conveniences become risky in P2:

- Title/name/latest selection is ambiguous once multiple works, same-name characters, or multiple
  persona versions exist.
- Durable service/API writes should require explicit IDs for source work, character, user,
  conversation, and persona version.
- Same-name characters across works should remain distinct until a shared identity model is
  designed.
- The current conversation model remains one user, one character, one persona version.
- Multi-character/group conversations need a separate participant model and are out of scope for
  early P2.
- Source evidence and chunk IDs should become easier to inspect through service responses.
- Memory scope should be visible in prompt/inspection output so user memory and relationship memory
  do not blur together.

P2 prerequisites:

- Add source-work and character discovery/inspection services before relying on remote callers to
  know IDs.
- Require explicit `persona_version_id` in durable service/API workflows, while CLI convenience
  defaults may remain local-only.
- Keep demo title reuse and display-name reuse explicitly CLI-demo behavior.
- Preserve evidence-backed canon. Evaluation and audit data must not directly rewrite canon,
  persona, or accepted memory.

## User, Workspace, And Audit Decisions

Task 04 accepted a minimal user concept and deferred workspace:

- `User` remains a local continuity identity, not an authenticated account.
- User memory and relationship memory stay private to a `user_id` + `character_id` pair.
- Early P2 should not add `Workspace`, membership, roles, permissions, billing, quotas, or
  multi-tenant isolation.
- Service/API writes should use explicit `user_id`; do not resolve durable workflows by
  `display_name`.
- Audit is required before exposing richer manual semantic-state changes through API/UI.

Minimum audit direction:

- Audit events should be append-only, structured, and linked to actor, operation, affected entity,
  reason, relevant IDs, before/after snapshots, and metadata.
- Manual memory review/edit/archive requires audit. Archive should gain an explicit reason when it
  moves beyond the current CLI-only behavior.
- Human canon claim review/correction requires audit and must stay evidence-backed or explicitly
  human-reviewed.
- Provider calls that affect semantic state should be linkable to `LLMRawOutput` through workflow
  context or audit records.
- Audit records explain state changes; they are not canon, persona, or memory state themselves.

## Runtime Observability Requirements

Task 03 mapped the current turn workflow and accepted the following P2 observability needs:

- Conversation turn inspection should navigate from conversation to messages, assistant context
  package, critic report, failure cases, created memories, and summary layers.
- Context package inspection should expand persona version, claim IDs, evidence refs, retrieved
  chunks, memory summaries, and source locations.
- Assistant response inspection should link to critic report and failure case records.
- Memory inspection should expose final memory IDs, scope, status, importance, reason, and
  conversation/user/character linkage.
- Benchmark failure inspection should follow OOC results to assistant message, context package,
  critic report, failure cases, and relevant traces where links exist.
- Retrieval failure inspection should resolve expected and retrieved chunk IDs, scores, diagnostics,
  and source chunk details.

Known observability gaps to address in or after P2:

- No durable turn/run correlation ID links runtime steps and traces.
- `LLMRawOutput` lacks first-class business-object foreign keys.
- Roleplay `generate_text` calls are not traced.
- Context package retrieval stores chunk IDs but not ranks, scores, embedding path, or query
  diagnostics.
- Memory curator/guard decisions are not persisted as separate inspectable records, especially for
  rejected candidates.
- Conversation summary updates are not linked to message ranges or previous summary versions.

Early P2 should close the service/read-path gaps first and plan correlation metadata without
rewriting trace persistence prematurely.

## CLI/API Shared Service Refactor Plan

Task 05 accepted gradual extraction from `src/personality_jelly/cli/main.py`:

- Keep parser, dispatch, and printing in CLI.
- Move repeated database/session/provider bootstrap into shared helpers.
- Move read-only repository assembly into inspection services.
- Move turn, summary, benchmark, and character/persona setup workflows behind structured service
  functions after inspection services are stable.
- Keep local filesystem cases-file import/export in CLI adapters.
- Keep DB migration/config commands CLI-only until an admin/security model exists.
- Keep memory review/edit/archive out of API-facing shared services until actor/audit rules are
  implemented.

The preferred package shape is a thin `personality_jelly.application` or
`personality_jelly.services` package. This snapshot recommends `application` because the new layer
will orchestrate use cases rather than replace domain service modules.

## P2 Acceptance Criteria

P2 is accepted when all of the following are true:

1. A thin application-service package exists and is documented as the shared boundary for CLI and
   future API adapters.
2. CLI commands continue to work through the service layer without changing existing default output
   keys or behavior, except for explicitly additive diagnostics such as memory IDs.
3. Shared bootstrap helpers cover database/session setup and provider/model role bundles for CLI
   and future API use.
4. Read-only inspection services return structured results for conversations, context packages,
   critic reports, failure cases, characters, claims, memories, LLM traces, OOC eval runs, and
   retrieval eval runs.
5. Context package inspection can optionally resolve linked claims, evidence refs, source chunks,
   memories, and persona version metadata.
6. Turn workflow services return all IDs needed for inspection: user message, assistant message,
   context package, critic report, rejected retry records, failure cases, and created memories.
7. Durable service writes use explicit IDs for source work, character, user, conversation, and
   persona version; demo-only reuse policies remain clearly isolated.
8. User memory and relationship memory are surfaced as distinct scopes in inspection results.
9. Manual memory review/edit/archive has an audit-ready design before it is exposed through API/UI;
   if implemented in P2, it records actor, reason, before/after state, and linked IDs.
10. Provider-driven semantic state changes have a planned linkable workflow context to
    `LLMRawOutput` records, even if full trace schema changes are deferred.
11. OOC and retrieval benchmark inspection supports failed-only review and export/regression
    workflows through structured service results while preserving CLI file workflows.
12. API error-model mapping is specified for lookup errors, validation errors, relationship
    conflicts, provider failures, provider output validation failures, and successful critic
    retry/log outcomes.
13. No semantic behavior is moved into CLI printers, future HTTP handlers, or ad hoc string
    checks.
14. Existing focused CLI/runtime/evaluation tests pass after each extraction wave, and the full
    suite passes before P2 implementation closeout.

## P2 Non-Goals

These remain out of scope for P2 implementation unless a later accepted plan explicitly changes the
phase:

- Production FastAPI deployment, OpenAPI polish, auth, permissions, accounts, API keys, billing,
  quotas, or multi-tenant workspace isolation.
- Production web UI or admin console.
- Workspace table, membership roles, and platform audit dashboards.
- Full multi-work canon policy, shared character identity graph, or cross-work evidence bundles.
- Multi-character/group conversation runtime.
- Graph/vector database integrations, GraphRAG/LightRAG, LangGraph orchestration, third-party
  memory systems, or external evaluation frameworks.
- Replacing existing structured semantic judges with keyword, regex, fixed-vocabulary, or
  string-containment checks.
- Making benchmark/evaluation output automatically rewrite canon, persona, memories, or runtime
  prompts.
- Turning the one-shot `demo` pipeline into a public product API.
- Exposing local file paths, local config, secrets, DB migration commands, or filesystem exports
  through public API handlers.

## Recommended Batch 04

Batch 04 should be an implementation batch named `batch_04_service_foundation`. It should not add
FastAPI yet. It should create the service foundation that makes a later API adapter low-risk.

Recommended order:

1. Application package skeleton, bootstrap resources, provider role bundles, and error-mapping
   helpers.
2. Read-only inspection services for conversation, context, critic/failure, character/claims,
   memories, traces, OOC eval, and retrieval eval.
3. CLI list/show commands migrated to inspection services with output compatibility tests.
4. Turn service wrapper with complete result IDs, including created memory IDs.
5. Summary service wrapper.
6. Benchmark service wrappers while keeping cases-file load/export in CLI.
7. Character/persona setup wrapper, keeping demo reuse policies CLI-only.
8. Audit model design spike or minimal audit payload implementation for manual memory operations,
   if Batch 04 has capacity after read/turn services.

Parallelism:

- Bootstrap and inspection-model design should start first and serially because they define shared
  types.
- Conversation/context/critic inspection, character/claim/memory inspection, and eval/retrieval
  inspection can proceed in parallel once shared result conventions exist.
- Turn/summary and benchmark wrappers should wait until bootstrap and relevant inspection results
  are merged.
- Character/persona setup should be last because it touches the broadest demo workflow.

See `plans/batch_04_service_foundation/BATCH_04_SERVICE_FOUNDATION.md` for task drafts.

## Human Review Needed

Before implementation starts, maintainers should confirm:

- Package name: `personality_jelly.application` versus `personality_jelly.services`.
- Whether CLI turn output should add `memory_ids` immediately or only expose them through the new
  service result.
- Whether `persona_version_id` should become required in all durable service workflows from the
  first Batch 04 task, or introduced after CLI compatibility work.
- Whether audit gets a physical table in Batch 04 or remains payload/design-only until API writes
  start.

## Verification

This closeout task changes documentation only. No automated tests are required.
