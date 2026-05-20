# Personality Jelly

Personality Jelly is an MVP for building and running high-fidelity AI character brains from novel text.

The first implementation phase focuses on stable engineering boundaries:

- canon and user memory separation
- source evidence tracking
- persona versioning
- replaceable LLM provider abstraction
- SQLite-first storage that can migrate toward PostgreSQL

## LLM provider

The real provider entrypoint is OpenAI-compatible and configured with environment variables:

```powershell
$env:PJ_LLM_PROVIDER = "openai-compatible"
$env:PJ_LLM_BASE_URL = "https://api.openai.com/v1"
$env:PJ_LLM_API_KEY = "<api-key>"
$env:PJ_LLM_MODEL = "<chat-model>"
```

Use `personality_jelly.llm.build_llm_provider(Settings())` to construct the configured provider.

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

Inspect character profile assets and canon claims:

```powershell
.\.venv\Scripts\pjelly.exe show character char_...
.\.venv\Scripts\pjelly.exe list claims --character-id char_... --status verified
```

Summarize a conversation into its stored context summary:

```powershell
.\.venv\Scripts\pjelly.exe summarize conversation conv_... --messages 20
```

Run the MVP OOC and canon-pollution benchmark against an existing character:

```powershell
.\.venv\Scripts\pjelly.exe eval ooc-benchmark --character-id char_...
```

Inspect, correct, or archive user memories:

```powershell
.\.venv\Scripts\pjelly.exe list memories --user-id user_... --character-id char_...
.\.venv\Scripts\pjelly.exe edit memory mem_... --content "用户喜欢夜里写作。"
.\.venv\Scripts\pjelly.exe archive memory mem_...
```

The default `demo` provider is still `stub`, so existing deterministic local demos do not need
network access or environment variables.

## Current project status

Last updated: 2026-05-20.

Personality Jelly is still in the "plan three MVP" phase: a single-work, single-protagonist
novel character brain with clear boundaries for later multi-agent and platform evolution.

Implemented:

- SQLite + SQLAlchemy repositories for source works, chunks, characters, canon claims, evidence,
  persona versions, conversations, messages, memories, context packages, critic reports, failure
  cases, and evaluation runs.
- TXT/Markdown ingestion with chapter/paragraph chunking and stable chunk IDs.
- Character creation, Reader extraction, Verifier canon validation, evidence references, and
  conflict recording.
- Persona compilation from verified canon claims.
- Runtime conversation flow with context-package assembly, roleplay generation, critic evaluation,
  optional retry, failure-case capture, memory curation, memory guard, and conversation summary.
- Structured interaction-mode classification through `InteractionModeClassification`; no local
  marker-based semantic mode inference remains.
- Semantic source retrieval in `retrieval/semantic.py`; configured embeddings rank chunks by vector
  similarity, while no-embedding fallback only uses character name/alias entity anchoring.
- Structured memory safety validation through `MemoryGuardDecision`; guard-unavailable memories are
  downgraded to `candidate` for review instead of being accepted.
- Structured benchmark case evaluation through `BenchmarkCaseEvaluation`; benchmark pass/fail is
  not mechanically derived from critic actions.
- CLI coverage for demo, turn, list, show, eval, archive, edit, and summarize.
- Full test suite currently passes: `68 passed`.

## Next development tasks

P0:

- Add database migrations. `create_all` is acceptable for the MVP loop, but schema evolution needs
  Alembic or an equivalent migration path before persistent data matters.
- Build the candidate-memory review workflow: list candidate memories, accept/reject them, and
  preserve review reasons.
- Add tracing for structured semantic operations: mode classifier, memory guard, benchmark
  evaluator, and future retrieval evaluators should record operation, schema, provider, model,
  parsed output, raw output, and validation errors.
- Tighten `CriticReport.suggested_action` into an explicit contract, preferably an enum or schema
  pattern, and document `accept/retry/log` semantics.

P1:

- Persist source chunk embeddings and avoid re-embedding every retrieval call.
- Add retrieval-quality benchmarks for recall, ranking, and empty-result fallback without using
  fixed word matching as the quality signal.
- Expand the benchmark library for OOC, canon pollution, memory pollution, mode confusion, and
  reality-adaptation failures.
- Improve conversation summary strategy so short-term scene state, user memory, relationship
  memory, and reflective memory cannot contaminate each other.
- Improve CLI diagnostics with dry-run, verbose tracing, model configuration display, and clearer
  batch benchmark output.

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
