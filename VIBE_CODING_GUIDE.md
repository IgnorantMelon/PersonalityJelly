# Personality Jelly Vibe Coding Guide

Last updated: 2026-05-26.

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
- Start from clean `dev`, create a scoped task branch, and commit only the task's changes there.
  Multi-agent task prompts may require pushing the task branch for coordinator review instead of
  merging back to `dev` directly.
- If a task branch already exists, inspect it and continue only if it is clearly the intended task
  branch.
- Follow the current post-Batch 05 direction unless a task explicitly changes phase. FastAPI and
  httpx are adopted only for the thin read-only API adapter and its tests; do not add write APIs,
  platform/auth/workspace features, graph/vector databases, LangGraph, unrelated new dependencies,
  or web UI work without an explicit later batch.
- Do not introduce keyword, regex, fixed-vocabulary, or string-containment semantic judgments.
- Add or update tests for behavior changes, run focused tests first, and run the full suite when
  shared behavior is touched.
- Final reports should include files changed, tests run and results, and any task-specific caveats.
- Current phase direction is post-Batch 05 planning. The read-only FastAPI adapter is closeout
  verified and remains limited to thin read-only adapters over `personality_jelly.application`;
  do not add write APIs, platform/auth/workspace features, or semantic behavior in API handlers
  without an explicit later batch.

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
  critic reports, failure cases, LLM raw outputs, OOC evaluation runs, and retrieval evaluation
  runs.
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
  character/claim/memory/source chunks, critic/failure/trace/eval records, turn workflow summary
  wrappers, summary and benchmark workflow wrappers, character/persona setup orchestration, and
  payload-only audit readiness models for manual memory operations.
- Batch 05 read-only FastAPI adapter is closeout verified: app factory, health check,
  database/session dependency, structured error envelope, and GET-only route families for
  conversation/context, character/claim/memory/source chunk, critic/failure/LLM trace, OOC eval
  runs, and retrieval eval runs. Handlers call application services and do not add write workflows.
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

1. Start from clean `dev`.
2. Create a scoped branch such as `feature/...`, `fix/...`, or `docs/...`.
3. Check `git status --short --branch` before editing.
4. Keep the branch focused on one topic.
5. Avoid unrelated refactors, formatting churn, and dependency additions.
6. Do not revert unrelated user or branch changes.
7. Add or update tests when behavior changes.
8. Run focused tests first when practical.
9. Run full `pytest` before submitting changes that touch shared behavior.
10. Commit on the task branch.
11. Follow the task-specific completion instruction:
    - for solo/local tasks, switch back to `dev`, merge with `git merge --no-ff <branch>`, run
      relevant tests again on `dev`, and leave the worktree clean;
    - for multi-agent task prompts that request coordinator review, do not merge into `dev`;
      push only the task branch to `origin` and report the branch and commit hash.

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

## Current Priority Backlog

P0:

- No open P0 items.

P1:

- No open P1 hardening items at this snapshot.
- Future OOC or retrieval regressions should still be captured first as explicit cases files before
  behavior changes.
- Continue preserving stable CLI `key=value` diagnostics when adding P2 surfaces.

P2:

- Batch 03 planning is complete and Batch 04 service foundation is implemented.
- Batch 05 read-only API adapter is complete and closeout verified.
- Batch 05 exposes only read-only endpoints over existing `application` inspection services:
  conversations, context packages, characters, claims, memories, critic reports, failure cases,
  LLM traces, OOC eval runs, and retrieval eval runs.
- Do not add write endpoints through HTTP without an explicit later implementation batch: no source
  ingest, character creation, turn execution, summary generation, benchmark execution, memory
  mutation, or audit persistence.
- Preserve explicit ID boundaries for source works, characters, users, conversations, persona
  versions, memories, evidence chunks, and eval records.
- Batch 06 is the next planning/readiness batch. It should narrow deferred API questions into safe
  future implementation contracts for write workflows, actor/auth/audit boundaries, API-level
  redaction, pagination/filter conventions, trace/workflow correlation, and closeout acceptance.
- Batch 06 itself should not implement write API routes unless a task explicitly changes from
  planning into implementation after the contracts are accepted.
- Keep workspace/auth/platform features, graph/vector databases, third-party memory systems, and
  production UI out of scope until the service foundation is stable.

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

