# CLI/API Shared Service Refactor Plan

Task: `plans/batch_03_p2_planning/05_shared_service_refactor_plan_prompt.md`
Branch: `planning/shared-service-refactor`
Scope: planning only; no source code, schema, migration, dependency, or test changes.

## Inputs Read

- `VIBE_CODING_GUIDE.md`
- `plans/batch_03_p2_planning/P2_PLANNING_ORCHESTRATION.md`
- Task 01: `plans/batch_03_p2_planning/01_fastapi_service_boundary_design.md`
- Task 02: `plans/batch_03_p2_planning/02_multi_entity_boundary_audit.md`
- Task 03: `plans/batch_03_p2_planning/03_runtime_observability_plan.md`
- Task 04 output was not available in the current checkout or fetched remote branch list.
- Current CLI and service modules listed in the task prompt.

## Summary

`src/personality_jelly/cli/main.py` is doing three jobs today:

1. CLI argument parsing and stable `key=value` printing.
2. Local runtime bootstrap: settings, database URL resolution, migrations, session creation,
   provider/model resolution, and transaction commits.
3. Request-shaped orchestration around existing domain services and repositories.

The first job should stay in `cli`. The second and third jobs should be extracted gradually into a
small application-service layer that both CLI and future API handlers can call. Existing domain
modules should remain the owners of behavior such as ingestion, extraction, persona compilation,
turn execution, memory guard, critic evaluation, and benchmark evaluation.

This is a refactor plan, not a request to implement FastAPI or rewrite the CLI. Batch 04 should
extract structured service functions behind the current CLI output, with tests proving CLI output
compatibility after each small move.

## Current Orchestration Blocks In CLI

| CLI block | Current role | Classification | Refactor target |
| --- | --- | --- | --- |
| Parser and dispatch (`_build_parser`, `main`, `_run_*` routers) | argparse setup and command routing | Keep CLI-only | Leave in `cli/main.py`; do not share with API. |
| Database/settings bootstrap (`Settings`, `_resolve_database_url`, engine/session/migrate calls) | Repeated local setup in nearly every command | Move to new application service module | `application.bootstrap` or `services.bootstrap` with CLI/API-safe factories. |
| Provider resolution (`_resolve_demo_provider`, `_resolve_embedding_provider`, `_resolve_embedding_config`) | Maps `stub`/`env` CLI flags to provider roles and model configs | Move to new application service module | `application.providers`; keep CLI flags as adapters into provider policy. |
| Demo persona bootstrap (`_prepare_demo_persona`) | Ingest/reuse source, create/reuse character, extract, verify, compile persona | Move to new application service module, but keep one-shot demo CLI-only | `application.demo` or split into `application.character_setup`; API should expose steps, not demo. |
| Demo user/conversation reuse (`_resolve_demo_user`, `_resolve_demo_conversation`) | Reuses user by display name and latest user-character conversation | Leave unchanged until later phase | Keep scoped to CLI demo until Task 04 user/workspace/audit model exists. |
| Turn execution (`_run_turn`, turn portion of `_run_demo`) | Provider setup, conversation lookup, `send_roleplay_turn`, commit, result printing | Move to new application service module | `application.conversations.run_turn`; CLI prints returned result. |
| Read-only inspection (`list/show conversations`, claims, memories, failure cases, context, critic, traces, eval runs) | Repository reads plus output shaping/printing | Move read assembly to new application service module | `application.inspection`; CLI keeps print functions. |
| Memory archive/edit/review | Repository writes for manual memory operations | Leave unchanged until later phase | Defer until Task 04 audit/ownership model because edits need actor/reason audit semantics. |
| Conversation summary command | Provider setup, `summarize_conversation`, commit, print summary | Move to existing runtime or new application service module | Keep summary behavior in `runtime`; add `application.conversations.summarize`. |
| OOC benchmark run/dry-run/show/export | Cases-file handling, provider setup, run service, report summary, export | Split: move execution/report assembly; keep filesystem export CLI-only | `application.benchmarks`; API receives structured cases instead of paths. |
| Retrieval benchmark run/dry-run/show/export | Cases-file handling, embedding provider setup, run service, diagnostics, export | Split: move execution/report assembly; keep filesystem export CLI-only | `application.benchmarks` or `application.retrieval_benchmarks`. |
| DB status/migrate | Local operational database commands | Keep CLI-only | Do not expose through public API without admin model. |
| Config show/check | Local configuration diagnostics | Keep CLI-only | Do not expose secrets/provider config through API in P2. |
| Formatting helpers (`_print_*`, `_json_block`, ratios) | CLI stable output | Keep CLI-only | May consume structured service results but should not be imported by API. |

## Minimal Service Layer Shape

Use a small package such as `src/personality_jelly/application/` or
`src/personality_jelly/services/`. The name matters less than the boundary:

- Application services may orchestrate existing modules and repositories.
- Application services may return dataclasses or Pydantic response-shaped models.
- Application services should not print.
- Application services should not parse `argparse.Namespace`.
- Application services should not own semantic judgment prompts or provider-specific behavior.
- CLI and API adapters should own transport-specific request parsing and response formatting.

Suggested foundation:

```text
personality_jelly/application/
  bootstrap.py          # settings -> database/session/provider resources
  demo.py               # CLI-only composite demo pipeline helpers
  characters.py         # source/character/persona setup orchestration
  conversations.py      # start conversation, run turn, summarize
  inspection.py         # read-only diagnostics assembled from repositories
  benchmarks.py         # OOC and retrieval run/dry-run/show assembly
  errors.py             # optional domain-to-adapter error normalization
```

This package should stay thin. Most behavior remains in existing modules:

- `ingestion` owns loading/chunking/persisting source works.
- `characters` owns character creation validation.
- `extraction` owns Reader and Verifier flows.
- `persona` owns persona compilation.
- `runtime` owns conversation creation, context assembly, turn generation, summary.
- `critic` and `memory` own semantic review and memory curation.
- `evaluation` owns benchmark case validation, execution, and report math.
- `storage` owns repositories and migrations.

## Service Shape By Workflow

### Ingestion / Demo Bootstrap

Move reusable pieces out of `_prepare_demo_persona`, but do not turn the whole `demo` command into
a public API workflow.

Candidate models:

- `SourceReusePolicy`: `create_new`, `reuse_by_title_for_cli_demo`.
- `CharacterSetupRequest`: `source_work_id`, `canonical_name`, `aliases`, `reuse_existing`.
- `PersonaBuildRequest`: `character_id`, provider role bundle, optional extraction limits.
- `DemoBootstrapRequest`: local path, character name, aliases, user display name, reuse flag.
- `DemoBootstrapResult`: `source_work`, `character`, `persona_version`, optional ingestion counts.

Recommended extraction:

- `application.characters.ensure_character_persona(...)` can call `create_character`,
  `run_reader_extraction`, `verify_candidate_claims`, and `compile_persona_version`.
- Keep title-based source reuse as explicitly CLI-demo policy. Task 02 identified title-only reuse
  as ambiguous for multi-work behavior, so future API requests should require `source_work_id` or
  structured source ingest input.

### Character Extraction And Persona Compilation

Existing service functions are already close to reusable:

- `run_reader_extraction`
- `verify_candidate_claims`
- `compile_persona_version`

Application layer should only sequence these into a single explicit operation when callers want
"build or rebuild this character's persona".

Candidate service:

- `build_character_persona(session, character_id, providers, model_configs) -> CharacterPersonaBuildResult`

Result fields:

- `character_id`
- `source_work_id`
- `candidate_claim_ids`
- `evidence_ref_ids`
- `verified_claim_ids`
- `conflict_ids`
- `persona_version_id`

Do not add broad source/canon redesign in this refactor. Multi-work policy belongs to a later P2
model task.

### Conversation Start And Turn Execution

Existing runtime behavior is reusable but CLI currently owns provider setup and transaction
boundaries.

Candidate services:

- `start_conversation(session, user_id, character_id, persona_version_id, interaction_mode)`.
- `run_conversation_turn(session, conversation_id, content, providers, model_configs,
  interaction_mode=None, retry_on_critic=False)`.
- `summarize_conversation_for_inspection(session, conversation_id, provider, model_config,
  max_messages)`.

Turn service result should mirror `RoleplayTurnOrchestrationResult` plus display-ready IDs:

- `conversation_id`
- `user_message_id`
- `assistant_message_id`
- `context_package_id`
- `interaction_mode`
- `critic_report_id`
- `critic_action`
- `retry_count`
- `rejected_assistant_message_id`
- `rejected_critic_report_id`
- `failure_case_ids`
- `memory_ids` and memory statuses

Task 03 called out that CLI turn output currently reports `memory_count` but not `memory_id`
values. Batch 04 can add service result fields first, then decide whether CLI output should add
new optional lines while preserving existing ones.

### Inspection / Read-Only Diagnostics

Read-only inspection is the safest first extraction because it reduces CLI/API duplication without
touching semantic workflows.

Candidate services:

- `list_conversations(session, limit, filters) -> ConversationListResult`
- `get_conversation_detail(session, conversation_id, message_limit) -> ConversationDetail`
- `get_character_detail(session, character_id) -> CharacterDetail`
- `list_claims(session, character_id, status=None, claim_type=None) -> ClaimListResult`
- `list_memories(session, user_id, character_id, scope=None, status=None) -> MemoryListResult`
- `get_context_package_detail(session, context_package_id, expand=False) -> ContextPackageDetail`
- `get_critic_report_detail(session, critic_report_id) -> CriticReportDetail`
- `list_failure_cases(session, filters) -> FailureCaseListResult`
- `get_failure_case_detail(session, failure_case_id) -> FailureCaseDetail`
- `list_llm_traces(session, filters) -> LLMTraceListResult`
- `get_llm_trace_detail(session, trace_id) -> LLMTraceDetail`
- `get_ooc_eval_run_detail(session, run_id, failed_only=False) -> OOCEvalRunDetail`
- `get_retrieval_eval_run_detail(session, run_id, failed_only=False) -> RetrievalEvalRunDetail`

The CLI can still print the exact existing `key=value` lines from these structured results. API
handlers can serialize the same result models.

Inspection should also address Task 02 and Task 03 gaps over time:

- Expand claim evidence with `chunk_id` and excerpt when requested.
- Expand context package claim, memory, and retrieved chunk IDs when requested.
- Include created memory IDs in turn inspection.
- Link OOC failed cases to assistant message, context package, critic report, and failure cases.
- Link retrieval failed cases to expected/retrieved chunk details.

### Benchmark Execution And Reporting

Execution functions already exist in `evaluation`. CLI still owns provider setup, cases-file path
loading/export, dry-run assembly, and printing.

Candidate services:

- `prepare_ooc_benchmark_cases(case_suite=None, explicit_cases=None)`.
- `dry_run_ooc_benchmark(session, character_id, persona_version_id, cases)`.
- `run_ooc_benchmark_workflow(session, character_id, provider, model_config,
  persona_version_id=None, test_suite=..., cases=...)`.
- `get_ooc_benchmark_report(session, run_id, failed_only=False)`.
- `prepare_retrieval_benchmark_cases(session, character_id, explicit_cases=None,
  max_cases=20, include_empty_case=True)`.
- `dry_run_retrieval_benchmark(session, character_id, cases, embedding_config)`.
- `run_retrieval_benchmark_workflow(session, character_id, provider, embedding_config,
  test_suite=..., cases=None, max_cases=20, include_empty_case=True)`.
- `get_retrieval_benchmark_report(session, run_id, failed_only=False)`.

Keep these CLI-only for Batch 04:

- Reading cases from local JSON paths.
- Writing exported cases files.
- Append/overwrite path behavior.

Future API should accept structured case bodies and return structured case exports, not local paths.

## Bootstrap And Transaction Boundary

Batch 04 should extract a reusable bootstrap without making it global state.

Candidate pieces:

- `DatabaseResources`: `database_url`, `engine`, `session_factory`.
- `open_database(settings, database_url=None, memory_db=False, migrate=True)`.
- `ProviderBundle`: roleplay, critic, memory curator, mode classifier, retriever providers.
- `ModelConfigBundle`: roleplay, critic, memory curator, mode classifier, retrieval embedding.

CLI adapter responsibilities:

- Parse flags.
- Choose `stub` or `env`.
- Decide which provider roles are enabled for a command.
- Convert `ValueError` / `LookupError` to `CliError`.
- Print results.

Application service responsibilities:

- Validate request-shaped values that are not CLI-specific.
- Call existing domain services.
- Return structured results.
- Leave commit/rollback policy explicit to the caller or a thin workflow wrapper.

API adapter responsibilities later:

- Validate HTTP request models.
- Build session/provider resources from configured app state.
- Call the same application services.
- Map errors to the Task 01 error envelope.
- Serialize structured results.

## CLI Compatibility Constraints

The refactor must preserve current CLI output as a contract:

- Keep existing `key=value` names stable.
- Keep line ordering stable where tests assert it or automation may parse it.
- Preserve multiline block markers such as `assembled_prompt<<END`, `raw_output<<END`,
  `parsed_output<<END`, and reason blocks.
- Preserve default provider behavior: `stub` remains default and deterministic.
- Preserve `--database-url` and `--memory-db` behavior, including their mutual exclusion.
- Preserve `--reuse-existing` demo behavior even though it is not API-safe.
- Preserve cases-file validation and export diagnostics for CLI commands.
- Preserve dry-run flags and `will_create_run=false` / provider-call diagnostics.
- Preserve error exit behavior: user-facing `CliError` returns exit code `2`.

Allowed compatibility-safe additions:

- Add new lines after existing turn output for `memory.{index}.id` or `memory_ids` if Batch 04
  decides to expose Task 03's memory-ID gap.
- Add optional verbose inspection flags for expanded claim evidence or context links, as long as
  default output stays compatible.

## Tests To Protect The Refactor

High-value existing tests:

- `tests/test_cli_demo.py::test_cli_demo_runs_end_to_end`
- `tests/test_cli_demo.py::test_cli_demo_reuses_existing_records_from_configured_database`
- `tests/test_cli_demo.py::test_cli_turn_sends_message_to_existing_conversation`
- `tests/test_cli_demo.py::test_cli_lists_and_shows_conversations`
- `tests/test_cli_demo.py::test_cli_runs_ooc_benchmark`
- `tests/test_cli_demo.py::test_cli_dry_runs_ooc_benchmark_without_persisting_run`
- `tests/test_cli_demo.py::test_cli_runs_lists_and_shows_retrieval_benchmark`
- `tests/test_cli_demo.py::test_cli_dry_runs_retrieval_benchmark_without_persisting_run`
- `tests/test_cli_demo.py::test_cli_reviews_candidate_memory`
- `tests/test_cli_demo.py::test_cli_summarizes_conversation`
- `tests/test_cli_demo.py::test_cli_shows_context_package_and_critic_report`
- `tests/test_cli_demo.py::test_cli_shows_character_profile_and_lists_claims`
- `tests/test_runtime_context.py::test_build_context_package_persists_prompt_with_persona_claims_and_memory`
- `tests/test_turn_orchestration.py::test_send_roleplay_turn_runs_optional_critic_and_memory_curator`
- `tests/test_evaluation_benchmark.py::test_run_ooc_benchmark_persists_run_and_case_results`
- `tests/test_retrieval_benchmark.py::test_run_retrieval_benchmark_persists_ranking_and_empty_result_metrics`

Recommended new tests when Batch 04 implements extraction:

- Application inspection service tests that assert structured result fields, independent of CLI
  printing.
- CLI golden-output compatibility tests around representative `list`, `show`, `turn`, and benchmark
  commands after each extraction step.
- Provider bootstrap tests for `stub`, `env` with missing model, and embedding fallback behavior.
- Transaction tests for service wrappers: successful workflows commit through caller path, provider
  failures do not silently commit partial API-visible state unless explicitly documented.
- Cases-file adapter tests remain CLI-specific; structured benchmark case validation remains in
  `evaluation` tests.

## Recommended Batch 04 Implementation Order

1. Extract bootstrap helpers without changing command behavior.

   Create database/session and provider bundle helpers that replace repeated CLI setup. Keep CLI
   output and tests unchanged.

2. Extract read-only inspection services.

   Start with conversation, context package, critic report, character, claims, memories, traces,
   failure cases, OOC eval run, and retrieval eval run detail assembly. This has the lowest
   behavioral risk and directly supports Task 01 and Task 03 API read paths.

3. Point CLI list/show commands at inspection services.

   Keep `_print_*` functions CLI-only. Run focused CLI tests after each command family.

4. Extract conversation turn workflow wrapper.

   Add `application.conversations.run_turn` around existing `send_roleplay_turn`, provider bundles,
   and result shaping. Preserve `pjelly turn` output. Consider adding memory IDs only as an additive
   output after compatibility is stable.

5. Extract summary workflow wrapper.

   Move `summarize conversation` orchestration behind a service while leaving `runtime.summary`
   behavior unchanged.

6. Extract benchmark workflow wrappers.

   Keep JSON cases-file load/export in CLI adapters. Move dry-run/run/report result assembly into
   application services for OOC and retrieval benchmarks.

7. Extract character/persona setup wrapper.

   Move the extraction/verification/persona compilation sequence behind an application service.
   Keep demo title-based reuse and display-name user reuse explicitly CLI-only.

8. Reassess manual memory review/edit/archive after Task 04 exists.

   Do not move these into API-facing shared services until actor, workspace, and audit rules are
   documented.

9. Only after the above, add FastAPI handlers in a later implementation batch.

   Handlers should be thin adapters over the extracted services and Task 01 error model.

## Risks And Guardrails

- Do not create a giant "god service" that knows every repository and prints CLI output.
- Do not import CLI helpers from API code.
- Do not let API handlers own provider resolution, transaction policy, or workflow sequencing.
- Do not move semantic prompts or validation schemas into application services.
- Do not make title/name/latest-persona reuse the default for API workflows.
- Do not change storage schemas or migrations as part of service extraction.
- Keep each extraction small enough that existing CLI tests can isolate regressions.

## Verification

No automated tests are required for this planning-only task unless source code changes are made.
