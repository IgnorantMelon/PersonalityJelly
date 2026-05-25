# Runtime Workflow Observability Plan

This is a planning-only note for Batch 03 Task 03. It maps the current runtime workflow and the
minimum inspection surface a future API or UI should expose. It does not propose runtime behavior,
trace persistence, schema, or semantic-judgment changes for this batch.

## Current Workflow Map

Primary turn orchestration is `send_roleplay_turn` in `src/personality_jelly/runtime/turn.py`.
The normal CLI path is `pjelly turn`, which prints the key IDs returned by the orchestration result.

1. The CLI resolves providers and model configs, then calls `send_roleplay_turn` with
   `conversation_id`, user `content`, optional explicit `interaction_mode`, and optional
   `retry_on_critic`.
2. `send_roleplay_turn` calls `runtime.roleplay.send_message`.
3. `send_message` persists the user `Message` unless it is a critic retry, then calls
   `build_context_package`.
4. `build_context_package` loads `Conversation`, resolves `interaction_mode`, loads the selected
   `PersonaVersion`, `Character`, verified `CanonClaim` records, accepted `Memory` records, and
   retrieved `SourceChunk` records, then persists a `ContextPackage`.
5. `send_message` sends the assembled prompt and current user message to the roleplay provider,
   persists the assistant `Message`, and links that assistant message to
   `context_package_id`.
6. If a critic provider is configured, `evaluate_message` creates a structured critic evaluation
   trace and persists a `CriticReport` linked to the assistant `message_id`.
7. If the critic suggests `retry`, `send_roleplay_turn` records a `FailureCase` for the rejected
   assistant response. With `retry_on_critic`, it generates a replacement assistant message using
   the already persisted user message, evaluates the replacement, and may record a second failure
   if the replacement is still unsafe.
8. If the critic suggests `log`, `send_roleplay_turn` records a review `FailureCase`.
9. If a memory curator provider is configured, `curate_memories_for_message` extracts structured
   memory candidates, runs memory guard decisions, and persists resulting `Memory` records under
   the conversation's `user_id` and `character_id`.
10. Conversation summary is not updated automatically inside `send_roleplay_turn`; the CLI
    `summarize conversation` command separately calls `summarize_conversation`, which records a
    structured summary trace and updates `Conversation.summary`.

Benchmark workflows reuse this same runtime surface:

- OOC benchmark runs create an isolated benchmark user and conversation, call
  `send_roleplay_turn` per case, persist `EvaluationRun` and `EvaluationCaseResult`, and record a
  structured semantic `BenchmarkCaseEvaluation` trace for each case judgment.
- Retrieval benchmark runs call `retrieve_source_chunks` directly and persist
  `RetrievalEvaluationRun` and `RetrievalEvaluationCaseResult`; they do not create conversation
  turns or structured `LLMRawOutput` traces. Embedding calls are not currently recorded in the
  trace table.

## Inspection Records And Linking IDs

The existing records already form most of the navigation graph:

| Record | Important fields | Current purpose |
| --- | --- | --- |
| `Conversation` | `id`, `user_id`, `character_id`, `persona_version_id`, `current_mode`, `summary` | Root for a user-character session and layered summary state. |
| `Message` | `id`, `conversation_id`, `role`, `content`, `context_package_id`, `created_at` | Stores user and assistant turns. Assistant messages link to their context package. |
| `ContextPackage` | `id`, `conversation_id`, `interaction_mode`, `persona_version_id`, `claim_ids`, `memory_ids`, `retrieved_chunk_ids`, `assembled_prompt` | Captures the prompt inputs used to generate an assistant response. |
| `PersonaVersion` | `id`, `character_id`, `source_work_id`, `source_claim_ids`, rule fields | Versioned character runtime persona used by a context package. |
| `CanonClaim` | `id`, `source_work_id`, `character_id`, `status`, `content` | Verified canon included in context. |
| `EvidenceRef` | `id`, `claim_id`, `chunk_id`, `excerpt`, `support_score` | Links claims back to source chunks. |
| `SourceChunk` | `id`, `source_work_id`, `chapter_index`, `paragraph_index`, `text` | Source evidence retrieved into context and benchmark cases. |
| `CriticReport` | `id`, `message_id`, risk fields, `suggested_action`, `reasons` | Structured review of one assistant message. |
| `FailureCase` | `id`, `conversation_id`, `user_message_id`, `assistant_message_id`, `context_package_id`, `critic_report_id`, `category`, `reason` | Persisted failure or review item generated from critic output. |
| `Memory` | `id`, `user_id`, `character_id`, `conversation_id`, `scope`, `status`, `content`, `importance`, `reason` | Long-term user or relationship memory result after curator and guard handling. |
| `LLMRawOutput` | `id`, `operation`, `schema_name`, `provider_name`, `model_name`, `raw_output`, `parsed_output`, `validation_errors` | Structured LLM trace record for semantic JSON tasks. |
| `EvaluationRun` | `id`, `character_id`, `persona_version_id`, `test_suite`, status and counts | OOC benchmark run root. |
| `EvaluationCaseResult` | `id`, `run_id`, `case_id`, `prompt`, `interaction_mode`, `assistant_message_id`, `critic_report_id`, `status`, `reasons`, `category` | Per-case OOC result linked back to runtime turn output. |
| `RetrievalEvaluationRun` | `id`, `source_work_id`, `character_id`, `test_suite`, `embedding_model`, status and counts | Retrieval benchmark run root. |
| `RetrievalEvaluationCaseResult` | `id`, `run_id`, `case_id`, `query`, `expected_chunk_ids`, `retrieved_chunk_ids`, scores and diagnostics | Per-case retrieval result linked to source chunks by ID. |

Current turn result printing already surfaces:

- `conversation_id`
- `context_package_id`
- `user_message_id`
- `assistant_message_id`
- `critic_report_id`
- `critic_action`
- `rejected_assistant_message_id`
- `rejected_critic_report_id`
- `failure_case.*.id`
- `memory_count`

The main missing turn-level link is the set of actual `memory_id` values created by the curator and
guard path. The `RoleplayTurnOrchestrationResult` contains `memories`, so this is a CLI/API exposure
gap rather than a workflow gap.

## Existing Inspection Surface

The CLI already provides useful read paths:

- `list conversations` and `show conversation` inspect conversation roots, recent messages, message
  IDs, assistant `context_package_id`, and parsed summary layers.
- `show context-package` exposes `interaction_mode`, `persona_version_id`, `claim_ids`,
  `memory_ids`, `retrieved_chunk_ids`, and the exact `assembled_prompt`.
- `list claims` exposes claim IDs and evidence counts for a character.
- `list memories`, `archive memory`, `edit memory`, and `review memory` inspect and manually manage
  memory records.
- `list failure-cases` and `show failure-case` expose critic failure records, linked messages,
  context package, critic report, and user/assistant text.
- `show critic-report` exposes risk fields, suggested action, and reasons.
- `list llm-traces` and `show llm-trace` expose structured trace operation, schema, provider/model,
  response schema, raw output, parsed output, and validation errors.
- `list eval-runs` and `show eval-run` expose OOC benchmark run counts plus each stored case's
  assistant message, conversation, context package, critic report, prompt, and reasons.
- `list retrieval-eval-runs` and `show retrieval-eval-run` expose retrieval benchmark run counts,
  expected chunks, retrieved chunks, ranking diagnostics, and reasons.

## Trace Coverage

Structured `LLMRawOutput` records currently cover these semantic JSON tasks:

- `runtime.mode.classify_interaction_mode` with `InteractionModeClassification`.
- `critic.evaluate_message` with `CriticEvaluation`.
- `memory.curator.extract_candidates` with `MemoryCuration`.
- `memory.guard.semantic_decision` with `MemoryGuardDecision`.
- `runtime.summary.conversation_summary` with `ConversationSummaryDraft`.
- `evaluation.benchmark.case_evaluation` with `BenchmarkCaseEvaluation`.

These traces preserve provider/model, response schema, raw output, parsed output, and validation
errors. This is the right judgment boundary for P2: keep semantic decisions model- or
embedding-backed and validated by schemas. Do not introduce keyword, regex, fixed-vocabulary, or
string-containment judges for observability.

Trace links that would be useful later, without changing P2 runtime behavior now:

- Add a general correlation ID or operation context that can link trace records to
  `conversation_id`, `message_id`, `context_package_id`, `critic_report_id`, `memory_id`,
  `evaluation_run_id`, or `case_result_id` without parsing raw prompts.
- Link interaction-mode classification traces to the `ContextPackage` they influenced.
- Link critic evaluation traces to the persisted `CriticReport`.
- Link memory curator traces to the assistant message and context package, and memory guard traces
  to the resulting candidate or persisted `Memory`.
- Link summary traces to the `Conversation` and summary update time.
- Link benchmark evaluator traces to `EvaluationRun` and `EvaluationCaseResult`.

## Navigation Paths For A Future API Or UI

Conversation turn to context package:

1. Start at `Conversation.id`.
2. Fetch messages ordered by `created_at`.
3. For each assistant `Message`, read `context_package_id`.
4. Fetch `ContextPackage.id` to inspect `interaction_mode`, persona, claim IDs, memory IDs,
   retrieved chunk IDs, and assembled prompt.
5. For retries, use `FailureCase` records by `conversation_id` to find rejected assistant messages
   and their separate context packages.

Context package to source chunks and claims:

1. Fetch `ContextPackage.claim_ids` and `retrieved_chunk_ids`.
2. For each claim, show `CanonClaim.content`, type/status, and all `EvidenceRef` records by
   `claim_id`.
3. For each evidence ref, load `SourceChunk` by `chunk_id`.
4. For retrieved chunks, load `SourceChunk` directly and show chapter/paragraph location and text.
5. Where a retrieved chunk also appears in evidence refs, display that it is both retrieved context
   and verified support.

Generated response to critic report and failure case:

1. Start at assistant `Message.id`.
2. Fetch `CriticReport` by `message_id`.
3. If `suggested_action` is `retry` or `log`, fetch `FailureCase` by `assistant_message_id` or by
   `critic_report_id`.
4. Show the linked `user_message_id`, `assistant_message_id`, `context_package_id`,
   `critic_report_id`, category, reason, and notes.
5. In benchmark runs, start from `EvaluationCaseResult.assistant_message_id` and
   `critic_report_id`; then follow the same message and failure-case links.

Memory write to curator and guard decisions:

1. Start from `Memory.id`, `conversation_id`, `user_id`, and `character_id`.
2. Use `conversation_id` plus created time to locate the likely assistant turn; future P2 should
   expose `memory_id` values in turn output so the UI can link directly from the turn result.
3. Inspect `Memory.scope`, `status`, `importance`, content, and reason. Guard rejection or
   candidate decisions are currently folded into `Memory.status` and appended reason text.
4. To inspect the semantic calls, filter traces by `memory.curator.extract_candidates` and
   `memory.guard.semantic_decision`. Today these are time/operation searches, not hard links.
5. Future API/UI should show curator candidates and guard decisions as first-class derived
   inspection details, while preserving the existing semantic guard rules.

Benchmark failed case to relevant traces or context:

1. Start at `EvaluationRun.id`, then list `EvaluationCaseResult` records and filter failed cases.
2. For each failed OOC case, follow `assistant_message_id` to the assistant message and
   `context_package_id`, and follow `critic_report_id` to the critic report.
3. Show the case prompt, requested `interaction_mode`, assistant content, critic risks, case
   evaluator status, and case reasons.
4. Find `evaluation.benchmark.case_evaluation` traces by operation and time. A future correlation
   ID should link them directly to `EvaluationCaseResult.id`.
5. For retrieval failures, start at `RetrievalEvaluationRun.id`, then inspect failed
   `RetrievalEvaluationCaseResult` records. Follow `expected_chunk_ids`, `retrieved_chunk_ids`, and
   `missing_expected_chunk_ids` to `SourceChunk` records and evidence refs. Retrieval case results
   already store enough chunk IDs for source-level debugging, but not the full candidate ranking
   beyond persisted retrieved IDs/scores.

## Observability Gaps That Matter For API/UI Debugging

P2-relevant gaps:

- No durable turn/run correlation ID ties together user message, context package, roleplay output,
  critic report, failure cases, memory curator, guard decisions, summary updates, and traces.
- `LLMRawOutput` has no business-object foreign keys or metadata, so UIs must infer trace links by
  operation and timestamp.
- Roleplay `generate_text` calls are not traced, so the generated assistant response can be viewed
  only through the persisted assistant `Message`, not as a provider raw-output record.
- Retrieval inside context package persistence stores only `retrieved_chunk_ids`, not ranks, scores,
  query text after augmentation, embedding model, fallback-vs-semantic path, or empty-result reason.
- Context packages list claim IDs but not evidence ref IDs; a UI can resolve them through claim IDs,
  but the exact evidence chain is one hop removed.
- Turn CLI output reports `memory_count` but not `memory_id` values, so memory write inspection
  requires separate list/filter commands.
- Memory guard decisions are collapsed into final memory status and reason. Rejected candidates
  that are not persisted as `Memory` records are hard to inspect after the turn.
- Critic retry creates a rejected message/report path, but there is no explicit parent retry group
  beyond `FailureCase` links and the orchestration result.
- Summary updates are separate from turns and have no direct link to the messages summarized or the
  previous summary version.
- OOC benchmark evaluator traces are not linked to case-result IDs, and retrieval benchmark results
  are not linked to trace or context records because they do not run through the context package.

Later platform observability gaps:

- No user/workspace/audit actor model for who inspected, edited, reviewed, archived, or exported
  records.
- No immutable audit trail for manual memory review, memory edit/archive history, benchmark case
  export, or future API actions.
- No request-level telemetry for latency, token counts, provider errors, retries, or cost.
- No streaming lifecycle events for a future UI to show in-progress steps.
- No retention, redaction, or access-control policy around raw prompts, raw LLM outputs, memories,
  and user messages.

## P2 Must-Haves

For the first P2 implementation batch, keep the observability target narrow:

- Define a reusable turn inspection response shape that returns `conversation`, recent `messages`,
  assistant `context_package`, `critic_report`, `failure_cases`, created `memories`, and summary
  layers by ID.
- Expose direct IDs for created memories in CLI/API turn results.
- Add an API/service read path for `ContextPackage` that resolves claim details, evidence refs,
  source chunks, memory summaries, and persona version metadata without changing generation.
- Add an API/service read path for an assistant message that resolves critic report and failure
  cases.
- Add an API/service read path for benchmark failed cases that follows OOC results to assistant
  message, context package, critic report, and relevant traces where links exist.
- Add an API/service read path for retrieval failed cases that resolves expected and retrieved chunk
  details plus evidence refs.
- Plan correlation metadata for future structured traces, but do not retrofit trace persistence in
  this planning task.
- Preserve current semantic judgment boundaries: interaction mode, critic review, memory guard,
  benchmark pass/fail, and retrieval quality must remain schema/model/evidence based.

## Later Platform Observability

Defer these until after the API/service boundary and minimum read paths are stable:

- First-class workflow run records with step events, status transitions, retry grouping, latency,
  token counts, provider request metadata, and cost.
- First-class persisted memory curator candidates and guard decisions, including rejected candidates
  that do not become `Memory` rows.
- Trace correlation fields and indexes across all structured LLM calls.
- Raw roleplay provider trace storage with retention and redaction controls.
- Summary versioning with message-range links and diffable layered summaries.
- Retrieval diagnostics that persist full ranked candidates, scores, embedding model, query text,
  and fallback/semantic path decisions.
- Workspace-level audit logs for manual review, edits, exports, and future API/UI operations.
- UI-specific streaming progress events and timeline visualization.

## Non-Goals For This Plan

- Do not change trace persistence or runtime behavior in Batch 03 Task 03.
- Do not add FastAPI, UI code, graph/vector databases, external observability frameworks, or new
  dependencies.
- Do not replace semantic judges with keyword, regex, fixed-vocabulary, or string-containment
  rules.
