# Personality Jelly

Personality Jelly is an MVP for building and running high-fidelity AI character brains from novel text.

The first implementation phase focuses on stable engineering boundaries:

- canon and user memory separation
- source evidence tracking
- persona versioning
- replaceable LLM provider abstraction
- SQLite-first storage that can migrate toward PostgreSQL

## Model configuration

The real provider entrypoint is OpenAI-compatible. Non-secret defaults can be stored in
`pjelly.toml`; copy `pjelly.example.toml` and edit the models and endpoints for your cloud
provider. The local `pjelly.toml` file is ignored by git.

```toml
[llm]
provider = "openai-compatible"
base_url = "https://api.openai.com/v1"
model = "gpt-4.1-mini"
timeout_seconds = 60
json_response_format = "json_schema"

[embedding]
provider = "openai-compatible"
base_url = "https://api.openai.com/v1"
model = "text-embedding-3-small"
timeout_seconds = 60
```

Keep API keys in `.env` or real environment variables:

```powershell
$env:PJ_LLM_API_KEY = "<api-key>"
$env:PJ_EMBEDDING_API_KEY = "<api-key>"
```

Environment variables still override `pjelly.toml`; use `PJ_CONFIG_FILE` to point to another TOML
file. If `PJ_EMBEDDING_PROVIDER`, `PJ_EMBEDDING_BASE_URL`, or `PJ_EMBEDDING_API_KEY` are omitted,
the embedding client falls back to the LLM provider endpoint and key.

Set `llm.json_response_format = "json_object"` for OpenAI-compatible providers that do not support
`response_format.type = "json_schema"` but do support JSON object mode. In that mode Personality
Jelly injects the Pydantic JSON Schema into the prompt and still validates the returned object.

Use `personality_jelly.llm.build_llm_provider(Settings())` to construct the configured provider.
Use `personality_jelly.llm.build_embedding_provider(Settings())` to construct the configured
embedding provider.

Inspect sanitized runtime configuration:

```powershell
.\.venv\Scripts\pjelly.exe config show
.\.venv\Scripts\pjelly.exe config check
```

Run the end-to-end CLI with the configured provider:

```powershell
.\.venv\Scripts\pjelly.exe demo .\path\to\novel.md --character 林霜 --provider env
```

The CLI uses `PJ_DATABASE_URL` by default, falling back to `sqlite:///personality_jelly.db`.
Use `--memory-db` for a one-shot isolated run, or `--reuse-existing` to reuse matching source,
character, persona, user, and conversation rows in a persistent database.

Continue an existing conversation with one more user turn:

```powershell
.\.venv\Scripts\pjelly.exe turn conv_... --message "我们继续聊。" --provider env
.\.venv\Scripts\pjelly.exe turn conv_... --message "你是谁？" --retry-on-critic
```

Conversation turns classify interaction mode automatically. Override it when needed:

```powershell
.\.venv\Scripts\pjelly.exe turn conv_... --message "我们一起写一段新剧情。" --interaction-mode co_creation
```

Find and inspect persisted conversations:

```powershell
.\.venv\Scripts\pjelly.exe list conversations
.\.venv\Scripts\pjelly.exe show conversation conv_... --messages 5
.\.venv\Scripts\pjelly.exe show context-package ctx_...
.\.venv\Scripts\pjelly.exe show critic-report cr_...
```

Inspect structured LLM traces:

```powershell
.\.venv\Scripts\pjelly.exe list llm-traces --operation memory.guard.semantic_decision
.\.venv\Scripts\pjelly.exe list llm-traces --with-errors
.\.venv\Scripts\pjelly.exe show llm-trace llmraw_...
```

Inspect character profile assets and canon claims:

```powershell
.\.venv\Scripts\pjelly.exe show character char_...
.\.venv\Scripts\pjelly.exe list claims --character-id char_... --status verified
```

Summarize a conversation into its stored context summary:

```powershell
.\.venv\Scripts\pjelly.exe summarize conversation conv_... --messages 20
```

`summarize conversation` and `show conversation` also print parsed `summary.*` fields for
short-term scene state, user memory candidates, relationship notes, and reflective notes.

Run the MVP OOC and canon-pollution benchmark against an existing character:

```powershell
.\.venv\Scripts\pjelly.exe eval ooc-benchmark --character-id char_...
.\.venv\Scripts\pjelly.exe eval ooc-benchmark --character-id char_... --case-suite expanded_boundaries
.\.venv\Scripts\pjelly.exe eval ooc-benchmark --character-id char_... --case-suite boundary_regression
.\.venv\Scripts\pjelly.exe eval ooc-benchmark --character-id char_... --dry-run
.\.venv\Scripts\pjelly.exe eval ooc-benchmark --character-id char_... --verbose
```

Run and inspect source retrieval quality benchmarks:

```powershell
.\.venv\Scripts\pjelly.exe eval retrieval-benchmark --character-id char_... --provider env
.\.venv\Scripts\pjelly.exe eval retrieval-benchmark --character-id char_... --dry-run
.\.venv\Scripts\pjelly.exe eval retrieval-benchmark --character-id char_... --verbose
.\.venv\Scripts\pjelly.exe list retrieval-eval-runs --character-id char_...
.\.venv\Scripts\pjelly.exe show retrieval-eval-run retrievaleval_...
```

Retrieval benchmark output includes aggregate `report.*` diagnostics for evidence cases,
empty-result probes, recall, ranking, and missing expected evidence chunks.

Inspect or apply database schema migrations:

```powershell
.\.venv\Scripts\pjelly.exe db status
.\.venv\Scripts\pjelly.exe db migrate
```

Inspect, correct, or archive user memories:

```powershell
.\.venv\Scripts\pjelly.exe list memories --user-id user_... --character-id char_...
.\.venv\Scripts\pjelly.exe list memories --user-id user_... --character-id char_... --status candidate
.\.venv\Scripts\pjelly.exe review memory mem_... --decision accept --reason "人工确认可保存。"
.\.venv\Scripts\pjelly.exe review memory mem_... --decision reject --reason "缺少稳定依据。"
.\.venv\Scripts\pjelly.exe edit memory mem_... --content "用户喜欢夜里写作。"
.\.venv\Scripts\pjelly.exe archive memory mem_...
```

The default `demo` provider is still `stub`, so existing deterministic local demos do not need
network access or environment variables.

## Current project status

Last updated: 2026-05-21.

Personality Jelly is still in the "plan three MVP" phase: a single-work, single-protagonist
novel character brain with clear boundaries for later multi-agent and platform evolution.

Implemented:

- SQLite + SQLAlchemy repositories for source works, chunks, source chunk embeddings, characters,
  canon claims, evidence, persona versions, conversations, messages, memories, context packages,
  critic reports, failure cases, LLM raw outputs, evaluation runs, and retrieval evaluation runs.
- Database schema migrations are tracked through `schema_migrations`; CLI database commands
  auto-apply pending migrations, and `pjelly db status/migrate` exposes explicit migration control.
- TXT/Markdown ingestion with chapter/paragraph chunking and stable chunk IDs.
- Character creation, Reader extraction, Verifier canon validation, evidence references, and
  conflict recording.
- Persona compilation from verified canon claims.
- Runtime conversation flow with context-package assembly, roleplay generation, critic evaluation,
  optional retry, failure-case capture, memory curation, memory guard, and conversation summary.
- Conversation summaries use structured layers for short-term scene state, user memory candidates,
  relationship notes, and reflective notes before being formatted into stored context text; CLI
  show/summarize output parses these layers back into separate `summary.*` fields for review.
- Structured interaction-mode classification through `InteractionModeClassification`; no local
  marker-based semantic mode inference remains.
- Semantic source retrieval in `retrieval/semantic.py`; configured embeddings rank chunks by vector
  similarity, persisted source chunk embeddings avoid repeated chunk embedding calls, and
  no-embedding fallback only uses character name/alias entity anchoring.
- Retrieval-quality benchmark runs persist recall, ranking, first-relevant-rank, retrieved chunk
  IDs, scores, and empty-result fallback outcomes without using fixed word matching as the quality
  signal; CLI run/show output derives aggregate reporting for evidence cases, empty probes,
  average recall, ranking score, and missing expected chunks.
- Runtime model settings can be loaded from gitignored `pjelly.toml` with `.env`/environment
  overrides; LLM and embedding cloud providers can be configured separately.
- OpenAI-compatible structured output supports both strict `json_schema` mode and `json_object`
  compatibility mode. In `json_object` mode, Personality Jelly injects the Pydantic schema into
  the prompt and still validates the returned object.
- Structured memory safety validation through `MemoryGuardDecision`; guard-unavailable memories are
  downgraded to `candidate` for review instead of being accepted.
- Candidate memories can be reviewed from the CLI and promoted to `accepted` or `rejected` with a
  recorded review reason.
- Structured benchmark case evaluation through `BenchmarkCaseEvaluation`; benchmark pass/fail is
  not mechanically derived from critic actions.
- OOC benchmark case suites include the stable `mvp_default` set, `expanded_boundaries`, and
  `boundary_regression` for OOC, canon pollution, memory pollution, mode confusion, reality
  adaptation, and high-risk prompt-boundary probes.
- Critic `suggested_action` is a domain enum with `accept`, `retry`, and `log` as the only valid
  workflow actions.
- Structured semantic operations now persist tracing records for the interaction-mode classifier,
  memory guard, and benchmark evaluator, including operation, schema, provider, model, raw output,
  parsed output, and validation errors.
- CLI trace inspection exposes persisted structured LLM traces through `list llm-traces` and
  `show llm-trace`, with filters for operation, schema, provider, model, and validation errors.
- CLI coverage for demo, turn, list, show, eval, archive, edit, and summarize. Benchmark eval
  commands support `--verbose` for per-case prompts, queries, retrieved IDs, scores, and reasons.
- Cloud smoke checks passed with DeepSeek `deepseek-v4-flash` using
  `llm.json_response_format = "json_object"` and ModelArts MaaS `bge-m3` embeddings. The observed
  embedding vector dimension is 1024.
- Full test suite currently passes: `113 passed`.

## Next development tasks

Recent P1 progress:

- Persisted source chunk embeddings and added schema migration `0002_source_chunk_embeddings`.
- Added retrieval-quality benchmark persistence and schema migration
  `0003_retrieval_evaluation`.
- Added `pjelly.toml`/`.env` model configuration, separate LLM and embedding provider construction,
  and sanitized `pjelly config show` diagnostics.
- Added `json_object` structured-output compatibility for OpenAI-compatible providers that do not
  support strict `json_schema`.
- Added CLI trace inspection for structured LLM raw outputs, including error-only filtering.
- Added an expanded OOC benchmark case suite selectable with `--case-suite expanded_boundaries`.
- Added a stronger OOC boundary regression suite selectable with `--case-suite boundary_regression`.
- Added layered conversation summary output to keep short-term state, user memory, relationship
  notes, and reflective notes separate.
- Added `pjelly config check` diagnostics for local provider construction without network calls.
- Added benchmark dry-run diagnostics and pass-rate summaries for OOC and retrieval eval CLI runs.
- Added aggregate retrieval benchmark report diagnostics in CLI run/show output.
- Added parsed conversation summary layer inspection in CLI show/summarize output.
- Added verbose per-case diagnostics for OOC and retrieval benchmark CLI runs.
- Added `.env` and local SQLite database ignores to reduce accidental secret/runtime-data commits.

P0:

- No open P0 items.

P1:

- Extend semantic tracing to future retrieval evaluators.
- Expand retrieval-quality benchmark cases beyond the default evidence-derived suite.
- Continue curating benchmark cases from observed failures; current OOC suites now include
  `mvp_default`, `expanded_boundaries`, and `boundary_regression`.
- Continue hardening downstream consumption of layered summaries after CLI layer inspection.
- Improve CLI diagnostics with clearer errors and richer batch benchmark output.

P2:

- Implement the FastAPI service boundary from `docs/06_api_contracts.md`, reusing the same service
  layer as the CLI.
- Prepare multi-work and multi-character boundaries: same-name characters, alias conflicts,
  cross-work canon, and persona-version selection.
- Add user/workspace/audit concepts for later platformization.
- Make the agent workflow more explicit and observable, drawing from LangGraph/ReAct where useful.
- Evaluate Mem0, Zep/Graphiti, LangGraph Memory, GraphRAG, and LightRAG only after the current canon
  and memory boundaries are stable.

## Development rules

- Do not develop directly on `dev`. Start every task from the latest `dev` with a scoped branch such
  as `feature/...`, `fix/...`, or `docs/...`.
- Before editing, check `git status --short --branch`. Keep each branch focused on one topic.
- Commit on the task branch, then merge back to `dev` with `git merge --no-ff <branch>`. Run the
  relevant tests again on `dev` and leave the worktree clean.
- Never revert unrelated work or user changes. Avoid broad refactors, formatting churn, and
  dependency additions unless the task genuinely requires them.
- All semantic judgment tasks must avoid fixed vocabulary, preset word lists, markers, regex
  keyword rules, and string-containment heuristics.
- Semantic judgments include interaction mode, memory safety, canon or roleplay contamination,
  benchmark pass/fail, retrieval intent, user preference, and relationship evolution.
- Use structured model outputs, embeddings/vector similarity, verified evidence chains, or human
  review for semantic decisions.
- Deterministic code is appropriate for non-semantic work: schema validation, enum branching, ID
  lookup, empty-field handling, explicit user overrides, database constraints, and workflow control
  after consuming structured model outputs.
- If a semantic judge/provider is unavailable, degrade conservatively to current mode, candidate
  review, or empty result. Do not silently accept risky content.
- Original canon can only come from source evidence and Verifier confirmation. User conversation,
  temporary roleplay, jokes, and co-created fiction must not rewrite canon or persona core.
- Long-term memories must pass Memory Curator and Memory Guard; guard-unavailable memories remain
  candidate until reviewed.
- New LLM tasks must define Pydantic schemas and validate `generate_json` outputs. Tests should
  verify structured-result consumption, not local keyword hits.
- Fake providers in tests must branch by schema title when a provider is used for multiple
  structured tasks.
