# Personality Jelly Vibe Coding Guide

Last updated: 2026-05-27.

This is the practical guide for future coding sessions. It condenses only the project direction,
engineering rules, and architecture choices that are currently adopted and still valid. If older
files under `docs/`, `plans/`, `solutions/`, or `references/` conflict with this guide, treat those
older notes as historical context.

## Documentation Boundary

Keep documentation roles separate:

- `README.md` is the public project overview. It should contain the project goal, current status,
  quick start, and a brief development plan.
- `VIBE_CODING_GUIDE.md` is the source of truth for coding agents and future implementation
  sessions. Put agent instructions, workflow rules, adopted architecture constraints, semantic
  judgment rules, testing expectations, non-goals, and current engineering priorities here.
- `plans/` may contain task-specific prompts for multi-agent development runs, but those prompts
  should point back to this guide for shared project rules instead of duplicating them.
- Historical notes under `docs/`, `solutions/`, or `references/` are background material, not active
  instructions, when they conflict with this guide.

Do not move agent workflow rules or implementation guidance into `README.md`.

## Coding Agent Baseline

All coding agents and task prompts must follow this baseline:

- Read this guide before task-specific plans or code edits.
- Treat `README.md` as public project overview only, not as an active implementation rulebook.
- Assume other agents or the user may have changed the worktree. Do not revert, rewrite, reformat,
  or move unrelated work.
- Keep edits tightly scoped to the assigned task and avoid broad cleanup.
- Start independent tasks from clean `dev`, create a scoped task branch, and commit only the task's
  changes there. For dependent multi-agent tasks, branch from the completed prerequisite task
  branch, or from a dependency integration branch when multiple prerequisite branches are needed.
  Completed task branches still flow back into `dev` through coordinator integration and
  verification; dependent development does not have to wait for that `dev` merge.
- If a task branch already exists, inspect it and continue only if it is clearly the intended task
  branch.
- Follow the current post-Batch 05 direction unless a task explicitly changes phase. FastAPI and
  httpx are adopted only for the thin read-only API adapter and its tests; do not add write APIs,
  platform/auth/workspace features, graph/vector databases, LangGraph, unrelated new dependencies,
  or web UI work without an explicit later batch.
- Do not introduce keyword, regex, fixed-vocabulary, or string-containment semantic judgments.
- Add or update tests for behavior changes, run focused tests first, and run the full suite when
  shared behavior is touched.
- Implementation batch task prompts should describe development work only. Do not include
  coordinator-only management tasks such as closeout, branch integration, release status updates, or
  pure verification as numbered batch task prompts; keep those as coordinator acceptance criteria or
  post-batch status work.
- Final reports should include files changed, tests run and results, and any task-specific caveats.
- Current phase direction is post-Batch 09 Provider-Backed API Planning closeout. Batch 09 selected
  Batch 10 as the next accepted implementation scope: implement `POST /source-works` first, then
  deterministic `POST /characters`. Provider-backed persona setup remains deferred. Do not add
  provider-backed persona setup, other provider-backed HTTP write routes, platform/auth/workspace
  features, or semantic behavior in API handlers outside the accepted Batch 10 plan, and keep
  handlers thin over `personality_jelly.application`.

## Multi-Agent Orchestration Mode

When a session uses a main agent plus worker/sub-agent model, keep responsibilities explicit:

- The main agent is the coordinator. It reads the shared guide and task prompts, checks current
  branch/worktree state, decomposes dependency order, assigns worker tasks, waits for worker
  completion or explicit blockers, reviews reported outputs, and coordinates accepted-branch
  integration.
- The main agent must not directly take over a worker's implementation plan just because a task is
  long-running or silent. Long periods without worker output are normal for coding tasks.
- Interrupt or replace a worker only when the worker explicitly stops, reports a blocker, completes,
  or the user redirects the work. If a worker stops before completing, the main agent should
  reassign the task to another worker or ask for direction instead of silently becoming the worker.
- Worker/sub-agents own concrete implementation inside their assigned branch or worktree. They must
  keep edits scoped to their task, avoid reverting unrelated work, run required focused tests, commit
  their branch, push when the prompt requires it, and report branch/commit/test status.
- Coordinator integration is a separate responsibility from worker implementation. The main agent
  may coordinate accepted branch merges into `dev` in dependency order and rerun validation, but
  dependency-branch development remains only an efficiency path and never replaces final `dev`
  integration review.

## Current Goal

Personality Jelly is in the scheme-three MVP phase: a single-work, single-protagonist novel
character brain with enough boundaries to evolve later into multi-character and platform use.

The target experience is:

- ingest TXT/Markdown novel text;
- extract and verify source-backed canon claims for one protagonist;
- compile a persona version from verified canon;
- let the character talk naturally with a real user while preserving personality, tone, and canon;
- keep lightweight user and relationship memories without polluting canon;
- expose critic reports, traces, benchmarks, and CLI diagnostics for debugging.

The project is not trying to become a generic assistant, a complete roleplay platform, or a graph
database system in the current phase.

## 项目总体规划

This is the top-level development outline from project start to intended maturity. It is a
directional map for sequencing work; task prompts and batch plans remain the implementation
contracts for individual branches.

1. MVP character brain foundation:
   - ingest TXT/Markdown novel text;
   - persist source works, chunks, characters, canon claims, evidence, persona versions,
     conversations, messages, memories, context packages, traces, failures, and eval runs;
   - support one source work and one primary protagonist while preserving IDs required for later
     expansion.
2. Canon and persona pipeline:
   - extract source-backed character facts;
   - verify canon claims through evidence and structured Verifier output;
   - compile versioned personas from verified canon;
   - keep unverified memory, scene state, and reflective notes out of canon.
3. Runtime conversation and memory:
   - classify interaction mode semantically;
   - assemble context packages from persona, source evidence, memories, and layered summaries;
   - generate roleplay or reality-chat responses through provider abstractions;
   - run critic, retry/failure capture, memory curation, memory guard, and layered summaries.
4. Quality and diagnostics hardening:
   - record structured LLM traces and raw outputs for traceable semantic workflows;
   - maintain OOC and retrieval benchmark suites plus curated regression assets;
   - expose CLI diagnostics for config, database state, conversations, context packages, traces,
     failures, memories, and eval runs;
   - turn observed failures into explicit benchmark cases before changing behavior.
5. Shared service foundation:
   - move reusable workflow and inspection behavior into `personality_jelly.application`;
   - keep CLI and API adapters thin;
   - preserve transport-neutral request/result models and explicit ID boundaries.
6. HTTP adapter growth:
   - first expose read-only inspection through FastAPI over application services;
   - plan write workflow, redaction, actor/audit, pagination, and trace-correlation contracts before
     implementing write routes;
   - add write APIs only after contracts and service prerequisites are accepted.
7. Product and platform evolution:
   - expand from single-work/single-protagonist workflows toward multi-work, multi-character, and
     multi-user support only after data boundaries remain stable under tests;
   - add auth/workspace/platform features, production deployment, UI, external vector stores,
     graph systems, or third-party memory systems only when they solve a proven bottleneck.

## 长期开发计划

After Batch 06 closeout, future development should stay incremental and evidence-driven:

- API implementation path:
  - Batch 08 API Workflow Persistence Foundation is closeout verified;
  - Batch 09 Provider-Backed API Planning is closeout accepted and selected Batch 10 to implement
    `POST /source-works` first, then deterministic `POST /characters`;
  - provider-backed `POST /characters/{character_id}/persona-setup-runs` is deferred until a later
    staged setup batch; turn execution, summary, benchmark execution, and cursor migration remain
    later candidates;
  - every provider-backed route must reuse Batch 08 persistent audit, workflow-run/link,
    idempotency/replay, and provider failure/partial-persistence contracts;
  - keep write handlers as adapters over `application` services rather than moving workflow logic
    into `api`.
- Single-character acceptance checkpoint:
  - place the first formal test-acceptance node for the single-character MVP after API completion,
    not immediately after Batch 06 planning closeout;
  - API completion means the accepted API implementation batches expose the required single-character
    workflows and inspection surfaces through thin adapters over `application` services, with
    redaction, pagination/filtering, audit expectations, and trace/workflow correlation resolved;
  - this checkpoint should validate the end-to-end single-character experience across ingest,
    character/persona setup, conversation turns, memory boundaries, diagnostics, and benchmarks
    before expanding into multi-work, multi-character, workspace, or platform concerns.
- Canon, memory, and retrieval quality:
  - keep canon writes evidence-backed and reviewer-friendly;
  - keep user/relationship memory separate from source canon;
  - expand benchmark cases before changing semantic behavior;
  - improve retrieval only with measurable recall/ranking diagnostics.
- Multi-entity evolution:
  - preserve `source_work_id`, `character_id`, `user_id`, `conversation_id`,
    `persona_version_id`, memory scope, and evidence IDs in every shared contract;
  - defer true multi-work, multi-character, and workspace semantics until the current single-entity
    paths are reliable through CLI, application services, and API contracts.
- Platform and dependency discipline:
  - do not introduce LangGraph, GraphRAG/LightRAG, external vector databases, third-party memory
    services, production UI, auth, billing, or deployment machinery as speculative groundwork;
  - evaluate those options only after a concrete project bottleneck and migration boundary are
    documented.

## 下一阶段开发计划

Batch 09 Provider-Backed API Planning is closeout accepted. It added planning contracts only and did
not add provider-backed routes, source behavior changes, schemas, migrations, source code, or tests.

Accepted Batch 09 planning artifacts live under `plans/batch_09_provider_backed_api_planning/`:

- `BATCH_09_PROVIDER_BACKED_API_PLANNING.md`
- `01_source_ingest_api_contract_prompt.md`
- `02_character_persona_setup_api_contract_prompt.md`
- `03_provider_backed_write_contract_matrix_prompt.md`
- `04_next_implementation_batch_plan_prompt.md`
- `05_batch_09_closeout_prompt.md`
- `01_source_ingest_api_contract.md`
- `02_character_persona_setup_api_contract.md`
- `03_provider_backed_write_contract_matrix.md`
- `BATCH_09_CLOSEOUT.md`

Current Batch 10 implementation plan lives under
`plans/batch_10_provider_backed_source_character_api/`:

- `BATCH_10_PROVIDER_BACKED_SOURCE_CHARACTER_API.md`
- `01_source_ingest_application_workflow_prompt.md`
- `02_source_ingest_api_route_prompt.md`
- `03_character_creation_workflow_route_prompt.md`

Accepted Batch 10 scope:

1. Implement the source ingest application workflow and `POST /source-works`.
2. Implement deterministic character creation and `POST /characters`.
3. Defer provider-backed `POST /characters/{character_id}/persona-setup-runs` until a later batch.

Do not add auth/workspace/platform features, cursor migrations, CORS, deployment, UI, queues,
external observability, uploads, URL fetches, embeddings, provider-backed persona setup, or other
provider-backed routes outside the accepted Batch 10 scope.

Batch 08 task prompts and closeout artifact live under `plans/batch_08_api_workflow_persistence/`:

- `BATCH_08_API_WORKFLOW_PERSISTENCE.md`
- `01_persistent_audit_event_storage_prompt.md`
- `02_workflow_run_correlation_persistence_prompt.md`
- `03_idempotency_replay_foundation_prompt.md`
- `04_provider_failure_partial_persistence_contracts_prompt.md`
- `05_audit_correlation_inspection_routes_prompt.md`
- `06_batch_08_closeout_verification_prompt.md`
- `BATCH_08_CLOSEOUT.md`

Batch 06 planning artifacts live under `plans/batch_06_api_write_readiness/`:

- `BATCH_06_API_WRITE_READINESS.md`
- `01_write_workflow_boundary_design_prompt.md`
- `02_actor_auth_audit_boundary_prompt.md`
- `03_api_redaction_policy_prompt.md`
- `04_pagination_filter_contract_prompt.md`
- `05_trace_workflow_correlation_prompt.md`
- `06_batch_06_acceptance_next_recommendation_prompt.md`
- `01_write_workflow_boundary_design.md`
- `02_actor_auth_audit_boundary.md`
- `03_api_redaction_policy.md`
- `04_pagination_filter_contract.md`
- `05_trace_workflow_correlation.md`
- `06_batch_06_acceptance_next_recommendation.md`

Current Batch 07 task prompts live under `plans/batch_07_api_write_foundation/`:

- `BATCH_07_API_WRITE_FOUNDATION.md`
- `01_redaction_profile_foundation_prompt.md`
- `02_correlation_error_envelope_foundation_prompt.md`
- `03_local_actor_audit_boundary_prompt.md`
- `04_conversation_creation_write_route_prompt.md`
- `05_manual_memory_write_routes_prompt.md`
- `06_batch_07_closeout_verification_prompt.md`
- `BATCH_07_CLOSEOUT.md`

Do not add provider-backed HTTP write routes outside the next accepted batch scope. Provider-backed
workflows require additional durable workflow correlation, redaction, partial-persistence, retry,
idempotency, and audit decisions before HTTP exposure.

## Current Adopted Stack

Use what the codebase already uses:

- Python `>=3.12,<3.14`
- `uv` for environment and dependency management
- Pydantic v2 for domain models, config, and structured LLM outputs
- SQLAlchemy 2 with SQLite for storage
- the in-repo `schema_migrations` migration system
- the in-repo LLM provider abstraction with `generate_text`, `generate_json`, and `embed_texts`
- OpenAI-compatible LLM and embedding provider support
- CLI-first workflows through `pjelly`
- Application-service workflows through `personality_jelly.application`
- FastAPI for the thin read-only HTTP adapter over application services
- httpx for API route tests
- pytest for regression tests

Do not introduce these as implementation dependencies unless a later task explicitly moves into
that phase and documents the tradeoff:

- LangGraph orchestration
- Qdrant, Chroma, Neo4j, GraphRAG, LightRAG, pgvector
- LiteLLM routing
- Letta, Mem0, Zep, Graphiti, LangGraph Memory
- DeepEval, Ragas, LangSmith
- complex Web UI or platform admin features

Those projects remain references for future design, not current dependencies.

## Current Implemented Surface

The project currently has:

- SQLite + SQLAlchemy repositories for source works, chunks, source chunk embeddings, characters,
  canon claims, evidence, persona versions, conversations, messages, memories, context packages,
  critic reports, failure cases, LLM raw outputs, OOC evaluation runs, retrieval evaluation runs,
  audit events, workflow runs/links, and idempotency records.
- Database migrations tracked with `schema_migrations`; CLI commands auto-apply pending migrations,
  with `pjelly db status` and `pjelly db migrate` available for explicit control.
- TXT/Markdown ingestion with chapter/paragraph chunking and stable chunk IDs.
- Character creation, Reader extraction, Verifier canon validation, evidence refs, conflict
  recording, and persona compilation from verified claims.
- Runtime conversation flow with context package assembly, semantic interaction-mode
  classification, roleplay generation, critic evaluation, optional retry, failure-case capture,
  memory curation, memory guard, and layered conversation summary. Layered summaries are rendered
  downstream with explicit boundaries so short-term scene state, unverified memory candidates,
  relationship notes, and reflective notes remain separate.
- Semantic source retrieval in `retrieval/semantic.py`; configured embeddings rank chunks by
  vector similarity, persisted source chunk embeddings avoid repeated chunk embedding calls, and
  fallback retrieval only uses character name/alias entity anchoring.
- OpenAI-compatible structured output in both strict `json_schema` mode and `json_object`
  compatibility mode, always followed by Pydantic validation.
- Structured semantic tracing for interaction-mode classification, memory guard, benchmark
  evaluator calls, and CLI investigation through list/show trace commands.
- CLI inspection for conversations, context packages, critic reports, characters, claims, memories,
  failure cases, LLM traces, OOC eval runs, retrieval eval runs, config, and database migrations,
  with validation diagnostics for benchmark cases-file and export workflows.
- OOC benchmark suites: `mvp_default`, `expanded_boundaries`, and `boundary_regression`.
- Retrieval benchmark run/show/dry-run, explicit JSON cases files, case export, append mode,
  failed-only filtering, and aggregate `report.*` / `cases_summary.*` diagnostics.
- Source-controlled curated benchmark assets under `benchmarks/ooc/` and `benchmarks/retrieval/`
  cover OOC observed-boundary cases and retrieval quality regressions.
- A thin `personality_jelly.application` layer now wraps shared orchestration and inspection
  behavior for CLI and API adapters. It includes bootstrap/provider role bundles, strict
  inspection result models, read-only inspection services for conversation/context,
  character/claim/memory/source chunks, critic/failure/trace/eval records, audit/workflow records,
  turn workflow summary wrappers, summary and benchmark workflow wrappers, character/persona setup
  orchestration, persistent audit/workflow/idempotency helpers, provider failure contracts, and
  local actor models for deterministic write operations.
- Batch 05 read-only FastAPI adapter is closeout verified: app factory, health check,
  database/session dependency, structured error envelope, and GET-only route families for
  conversation/context, character/claim/memory/source chunk, critic/failure/LLM trace, OOC eval
  runs, and retrieval eval runs. Handlers call application services and do not add write workflows.
- Batch 07 deterministic write API foundation is closeout verified: `POST /conversations` plus
  manual memory review/edit/archive routes stay local-first and do not invoke providers.
- Batch 08 workflow persistence foundation is closeout verified: deterministic writes persist audit
  events, workflow runs/links, and idempotency records; provider failure/partial-persistence
  contracts are normalized and redacted; `/audit-events` and `/workflow-runs` provide read-only
  diagnostics; no provider-backed write route was added.
- Batch 05 closeout verification status: focused API route tests passed (`34 passed`), focused CLI
  inspection tests passed, and the full test suite passed at closeout: `233 passed, 3 warnings`.

## Data Boundaries

Keep these boundaries strict:

- Canon data comes only from source evidence plus Verifier confirmation or explicit human review.
- Persona runtime data is compiled from verified canon claims and versioned as `PersonaVersion`.
- User memory is private to a user-character pair.
- Relationship memory belongs to one user-character relationship and must not rewrite original
  character relationships.
- Session summary and reflective notes support continuity but are not canon.
- Evaluation data records failures, benchmark results, traces, and diagnostics; it can guide future
  changes but must not directly rewrite canon.

Important IDs and fields must remain part of core data flow:

- `source_work_id`
- `character_id`
- `user_id`
- `conversation_id`
- `persona_version_id`
- `memory_scope`
- `interaction_mode`
- source `chunk_id` / evidence refs

Current interaction modes are:

- `reality_chat`
- `roleplay_scene`
- `co_creation`
- `meta_discussion`

## Module Boundaries

Keep service logic aligned with the existing modules:

- `ingestion`: load text, chunk text, create source work/chunks.
- `characters`: create and inspect character records.
- `extraction`: Reader extraction and Verifier validation.
- `persona`: compile verified claims into persona versions.
- `retrieval`: retrieve source chunks using semantic embeddings or conservative fallback.
- `runtime`: create users/conversations, classify mode, build context, generate turns, summarize.
- `critic`: structured response review and suggested workflow action.
- `memory`: curate and guard long-term memory candidates.
- `evaluation`: OOC and retrieval benchmarks, reports, cases files.
- `storage`: ORM, mappers, repositories, migrations.
- `llm`: provider abstraction, OpenAI-compatible implementation, tracing.
- `application`: transport-neutral orchestration and read-only inspection services shared by CLI
  and API adapters. Keep this layer thin; it may coordinate repositories and existing
  domain services, but it must not own prompts, semantic judgment rules, or CLI/HTTP formatting.
- `cli`: orchestration and human-readable diagnostics only; reusable behavior belongs in service
  modules when practical.
- `api`: HTTP adapter only. It should validate request/response models, acquire sessions,
  call `application` services, and map errors. It must not duplicate workflow logic or perform
  semantic judgments.

Avoid hard-coding current MVP assumptions into shared code. A feature may be single-work and
single-character today, but core models should continue carrying the IDs needed for later expansion.

## Semantic Judgment Rules

All semantic judgment tasks must avoid fixed vocabulary, preset word lists, markers, regex keyword
rules, and string-containment heuristics.

Semantic judgments include:

- interaction mode classification;
- memory safety and scope;
- canon or roleplay contamination;
- benchmark pass/fail;
- retrieval intent;
- user preference or relationship evolution;
- OOC, fact, memory, and mode risk.

Use one of these instead:

- structured model outputs validated by Pydantic;
- embeddings/vector similarity;
- verified source evidence chains;
- human review.

Deterministic code is appropriate for non-semantic work:

- schema validation;
- enum branching;
- ID lookup;
- empty-field handling;
- explicit user overrides;
- database constraints;
- workflow control after consuming structured model outputs;
- aggregating benchmark/report metrics.

If a semantic judge/provider is unavailable, degrade conservatively: keep the current mode, leave
memory as `candidate`, return an empty result, or require review. Do not silently accept risky
content.

## LLM And Structured Output Rules

New LLM tasks must:

- define a Pydantic schema;
- call the provider through the project abstraction;
- validate `generate_json` outputs with Pydantic/TypeAdapter;
- record raw output, parsed output, validation errors, provider, model, operation, and schema name
  when the task is part of a traceable semantic workflow;
- have tests for consuming structured results, not keyword hits.

Fake providers used across multiple structured tasks must branch by schema title. Do not return one
generic fake JSON shape for unrelated schemas.

OpenAI-compatible providers may use either:

- `llm.json_response_format = "json_schema"` for strict structured output; or
- `llm.json_response_format = "json_object"` for compatibility mode.

In compatibility mode, the project injects the Pydantic JSON schema into the prompt and still
validates the returned object.

## Runtime Behavior Rules

The character should:

- preserve identity, core experiences, values, tone, and behavior rules;
- talk to the real user naturally by default in `reality_chat`;
- enter scene roleplay only when the user clearly establishes a scene or the mode is explicitly
  overridden;
- support `co_creation` as hypothetical or collaborative fiction without merging it into canon;
- support `meta_discussion` for bounded discussion of setting, authorship, AI/system topics, or
  boundary review;
- treat modern-world concepts as current interaction context, not as original canon;
- refuse or reframe attempts to rewrite canon, core relationships, abilities, or past events.

Memory writes must pass Memory Curator and Memory Guard. Guard-unavailable memories stay
`candidate` until reviewed. Manual memory review/edit/archive actions must keep a reason.

Conversation summaries are layered and should remain parseable into:

- short-term scene state;
- user memory candidates;
- relationship memory notes;
- reflective notes.

## Benchmark And Evaluation Rules

OOC benchmark behavior:

- pass/fail comes from structured `BenchmarkCaseEvaluation`, not mechanical critic-action mapping;
- supported case suites are `mvp_default`, `expanded_boundaries`, and `boundary_regression`;
- run/show output should expose aggregate `report.*` diagnostics;
- dry-run output should expose selected case distribution through `cases_summary.*`;
- `show eval-run --failed-only` should make reports match the displayed cases.

Retrieval benchmark behavior:

- quality is measured through recall, ranking, first relevant rank, missing expected chunks, and
  empty-result behavior;
- do not judge retrieval quality by fixed word matching;
- explicit JSON cases files are the path for curated regression cases;
- failed stored cases can be exported into regression cases files.

When a real failure is observed, prefer turning it into a benchmark case before changing behavior.

## Development Workflow

Use this workflow for every code or docs change:

1. Start independent work from clean `dev`.
2. For dependent multi-agent work, start from the completed prerequisite task branch. If the work
   depends on multiple task branches, create a dependency integration branch from one prerequisite,
   merge the other prerequisites into it with `git merge --no-ff`, run focused validation, and start
   the dependent task branch from that integration branch.
3. Create a scoped branch such as `feature/...`, `fix/...`, or `docs/...`.
4. Check `git status --short --branch` before editing.
5. Keep the branch focused on one topic.
6. Avoid unrelated refactors, formatting churn, and dependency additions.
7. Do not revert unrelated user or branch changes.
8. Add or update tests when behavior changes.
9. Run focused tests first when practical.
10. Run full `pytest` before submitting changes that touch shared behavior.
11. Commit on the task branch.
12. Follow the task-specific completion instruction:
    - for solo/local tasks, switch back to `dev`, merge with `git merge --no-ff <branch>`, run
      relevant tests again on `dev`, and leave the worktree clean;
    - for multi-agent task prompts that request coordinator review, do not merge into `dev`;
      push only the task branch to `origin` and report the branch and commit hash.
13. Coordinator integration still merges accepted task branches into `dev` in dependency order and
    reruns the required validation on `dev`. Branching dependent work from prerequisite branches is
    an efficiency path, not a replacement for final `dev` integration review.

Useful commands:

```powershell
git status --short --branch
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\pjelly.exe config show
.\.venv\Scripts\pjelly.exe config check
.\.venv\Scripts\pjelly.exe db status
```

## Current CLI Practices

The CLI is the current product surface. Maintain stable, script-friendly `key=value` diagnostics.

Common commands include:

```powershell
.\.venv\Scripts\pjelly.exe demo .\path\to\novel.md --character 林霜 --provider env
.\.venv\Scripts\pjelly.exe turn conv_... --message "我们继续聊。"
.\.venv\Scripts\pjelly.exe list conversations
.\.venv\Scripts\pjelly.exe show conversation conv_... --messages 5
.\.venv\Scripts\pjelly.exe summarize conversation conv_... --messages 20
.\.venv\Scripts\pjelly.exe list llm-traces --with-errors
.\.venv\Scripts\pjelly.exe eval ooc-benchmark --character-id char_... --case-suite boundary_regression
.\.venv\Scripts\pjelly.exe show eval-run eval_... --failed-only
.\.venv\Scripts\pjelly.exe eval retrieval-benchmark --character-id char_... --dry-run
.\.venv\Scripts\pjelly.exe show retrieval-eval-run retrievaleval_... --failed-only --export-cases-file .\failed-retrieval-cases.json
```

The default provider remains `stub`, so local deterministic demos and tests should not require
network access.

## Non-Goals For The Current Phase

Do not build these unless the task explicitly changes phase:

- full multi-work management;
- multi-character operations backend;
- multi-tenant permissions;
- payments, billing, limits;
- complete GraphRAG or graph database integration;
- automatic optimizer changes going directly live;
- production Web UI;
- large-scale concurrency work.

The immediate project value is a reliable, inspectable character brain, not platform breadth.

Batch 10 closeout note: the source/character API is now implemented and merged on `dev`. Batch 11
should start from that accepted state and add only staged provider-backed persona setup.
