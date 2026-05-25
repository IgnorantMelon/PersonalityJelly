# Multi-Work / Multi-Character Boundary Audit

Task: `plans/batch_03_p2_planning/02_multi_entity_boundary_audit_prompt.md`
Branch: `planning/multi-entity-boundary-audit`
Scope: audit only; no schema, migration, repository contract, source behavior, or test changes.

## Summary

The current codebase is still intentionally MVP-shaped around one source work and one active
protagonist per workflow, but the core relational model already carries most P2-critical IDs:
`source_work_id`, `character_id`, `user_id`, `conversation_id`, `persona_version_id`,
`interaction_mode`, memory `scope`, and source chunk evidence IDs.

The main P2 risk is not missing columns in the central runtime tables. The larger risk is that
several service and CLI workflows resolve "the current thing" by title, character name, latest
persona version, or latest user-character conversation. Those defaults are convenient for the CLI
demo path, but they will become ambiguous once a workspace contains same-title works, same-name
characters across works, multiple persona versions in production, or multiple conversations per
user-character pair.

## ID Propagation Snapshot

| ID / boundary | Current preservation | Notes |
| --- | --- | --- |
| `source_work_id` | Preserved on `SourceChunk`, `Character`, `CanonClaim`, `PersonaVersion`, and retrieval eval runs. | Runtime context derives the active work from `Character.source_work_id`; OOC eval runs do not store source work directly. |
| `character_id` | Preserved on claims, persona versions, conversations, memories, OOC eval runs, and retrieval eval runs. | Most service entry points require character ID, which is P2-friendly. |
| `user_id` | Preserved on conversations and memories. | No workspace or account ownership layer exists yet. |
| `conversation_id` | Preserved on messages, context packages, memories, failure cases, and CLI turn/show flows. | LLM trace rows do not directly carry conversation ID. |
| `persona_version_id` | Preserved on conversations, context packages, and OOC eval runs. | Several APIs default to latest persona when the caller omits it. |
| `memory_scope` | Preserved as `Memory.scope`; enum distinguishes user, relationship, session, and reflective memory. | Context prompt currently flattens accepted user and relationship memories into one section. |
| `interaction_mode` | Preserved on conversation current mode, context packages, OOC case results, and memory guard prompt input. | Conversation `current_mode` is read during classification but is not updated after a turn. |
| source `chunk_id` / evidence refs | Evidence refs point to `chunk_id`; context packages and retrieval eval case results store retrieved chunk IDs. | CLI claim listing shows evidence count but not evidence chunk IDs. |

Grounding:

- Domain models carry the core IDs on `Character`, `CanonClaim`, `EvidenceRef`, `PersonaVersion`,
  `Conversation`, `Memory`, `ContextPackage`, `EvaluationRun`, and `RetrievalEvaluationRun`
  (`src/personality_jelly/domain/models.py:62`, `:70`, `:82`, `:98`, `:118`, `:138`, `:151`,
  `:201`, `:228`).
- ORM tables and indexes align with those IDs, including work-scoped chunks/characters, indexed
  claims, indexed memories by user-character-scope-status, context package ID arrays, OOC eval
  character-persona index, and retrieval eval source-work/character fields
  (`src/personality_jelly/storage/orm.py:31`, `:71`, `:85`, `:180`, `:203`, `:272`, `:317`).
- Runtime context starts from `conversation_id`, loads conversation, persona, character, verified
  claims, accepted memories, retrieves chunks from the character's work, and persists a
  `ContextPackage` with mode, persona version, claim IDs, memory IDs, and retrieved chunk IDs
  (`src/personality_jelly/runtime/context.py:35`, `:46`, `:55`, `:57`, `:61`, `:66`, `:75`).

## Major Single-Work Assumptions

1. Demo reuse resolves a source work by title only.

   `_prepare_demo_persona` uses the source file stem as title and calls
   `SourceWorkRepository.find_by_title` when `--reuse-existing` is enabled
   (`src/personality_jelly/cli/main.py:2535`, `:2543`, `:2545`). The repository returns the newest
   matching title without considering author, file path, workspace, source hash, language, or
   caller intent (`src/personality_jelly/storage/repositories.py:91`). In P2, two works with the
   same title can make demo reuse attach extraction, persona, user, and conversation reuse to the
   wrong work.

2. Extraction and retrieval are single-work per character.

   Reader extraction loads chunks from `character.source_work_id` and passes that same work ID into
   claim creation (`src/personality_jelly/extraction/service.py:27`, `:36`, `:39`, `:42`). Runtime
   retrieval also uses `character.source_work_id` (`src/personality_jelly/runtime/context.py:66`,
   `:68`; `src/personality_jelly/retrieval/semantic.py:30`, `:43`). This is correct for the current
   MVP, but it blocks cross-work canon, anthology characters, remakes, translations, or merged
   evidence sets unless P2 adds an explicit work-set or source-selection boundary.

3. Persona compilation assumes verified claims for one character are sufficient work scope.

   `compile_persona_version` lists verified claims by `character_id` only and then stamps the
   persona with `character.source_work_id` (`src/personality_jelly/persona/compiler.py:30`, `:38`,
   `:90`, `:97`). Today `Character` is work-scoped, so this is consistent. In a future shared
   character identity that spans works, persona compilation must not silently collect all claims
   for a global character without a selected work or canon policy.

4. Retrieval benchmark cases are work-local through the character.

   Default retrieval cases are built from verified claims for a character and evidence refs, and
   runs persist `source_work_id=character.source_work_id`
   (`src/personality_jelly/evaluation/retrieval_benchmark.py:304`, `:321`, `:354`, `:365`, `:373`,
   `:388`). This is ready for per-work retrieval evaluation, but not for cross-work retrieval
   quality without an explicit multi-work test surface.

## Major Single-Character Assumptions

1. Character uniqueness is per source work, by canonical name only.

   `create_character` rejects duplicate canonical names within one work
   (`src/personality_jelly/characters/service.py:17`, `:33`, `:37`). This permits same-name
   characters across works, which is good for P2, but there is no alias collision check or
   disambiguation model. Same-work characters with overlapping aliases can confuse fallback
   retrieval and human CLI selection.

2. Runtime conversations are one user, one character, one persona version.

   `Conversation` contains one `user_id`, one `character_id`, and one `persona_version_id`
   (`src/personality_jelly/domain/models.py:118`). `create_conversation` accepts one character and
   validates that the selected persona belongs to that character
   (`src/personality_jelly/runtime/conversation.py:41`, `:56`, `:60`, `:65`). Multi-character
   scenes or group chats will need a new participant model rather than overloading this table.

3. Context assembly builds one persona and one character viewpoint.

   `build_context_package` loads a single persona and character from the conversation and retrieves
   only that character's accepted memories and source chunks
   (`src/personality_jelly/runtime/context.py:55`, `:56`, `:61`, `:66`). The prompt section names
   one "Persona Core Self"; there is no slot for multiple active characters or turn ownership.

4. OOC evaluation creates one benchmark user and one conversation for one character.

   `run_ooc_benchmark` resolves a single character and persona, creates one synthetic benchmark
   user, one conversation, and records case results for that run
   (`src/personality_jelly/evaluation/benchmark.py:473`, `:483`, `:498`, `:508`, `:513`, `:551`).
   This is useful for single-character regression, but multi-character evaluation will need case
   schema fields for active speaker(s), target character, and expected participant boundaries.

## ID Propagation Risks

1. "Latest persona" defaults are ambiguous.

   `create_conversation` defaults to `latest_for_character` when `persona_version_id` is omitted
   (`src/personality_jelly/runtime/conversation.py:53`, `:56`). OOC benchmark does the same
   (`src/personality_jelly/evaluation/benchmark.py:485`, `:488`), and CLI helper code exposes a
   dry-run resolver with the same behavior (`src/personality_jelly/cli/main.py:1856`, `:1859`).
   This is acceptable in the CLI MVP, but API/UI workflows should require an explicit persona
   version for repeatable conversations, evals, and audit records.

2. Demo conversation reuse ignores persona version.

   `_resolve_demo_conversation` reuses `latest_for_user_character(user_id, character_id)` when
   `--reuse-existing` is set (`src/personality_jelly/cli/main.py:2609`, `:2618`). If a new persona
   version is compiled for the same user-character pair, demo reuse may continue an old
   conversation tied to an older `persona_version_id`.

3. LLM raw traces lack direct entity foreign keys.

   `LLMRawOutput` stores operation, schema, provider, model, raw output, parsed output, and
   validation errors, but not `source_work_id`, `character_id`, `user_id`, `conversation_id`,
   `message_id`, or `context_package_id` as first-class columns
   (`src/personality_jelly/domain/models.py:188`; `src/personality_jelly/storage/orm.py:251`).
   Some prompts include IDs, but trace lookup is mostly by operation/provider/model
   (`src/personality_jelly/storage/repositories.py:511`). P2 audit and workspace views will need a
   joinable trace context or separate workflow event table.

4. OOC eval runs do not store `source_work_id`.

   `EvaluationRun` stores `character_id` and `persona_version_id` but not source work
   (`src/personality_jelly/domain/models.py:201`; `src/personality_jelly/storage/orm.py:279`).
   Since persona versions do store `source_work_id`, this is recoverable, but dashboards that
   compare evals by work need an extra lookup. Retrieval eval runs already store source work
   directly (`src/personality_jelly/domain/models.py:228`; `src/personality_jelly/storage/orm.py:317`).

5. Evidence refs preserve chunk IDs internally, but CLI claim listing hides them.

   `EvidenceRef` stores `chunk_id`, and extraction rejects unknown chunk IDs from the Reader
   (`src/personality_jelly/domain/models.py:82`; `src/personality_jelly/extraction/reader.py:92`).
   `list claims` loads evidence refs but prints only `evidence_count`, not the evidence chunk IDs
   or excerpts (`src/personality_jelly/cli/main.py:1090`, `:1096`, `:1101`). Downstream automation
   cannot reconstruct source-backed claim evidence from that CLI output alone.

6. Context package stores ID arrays without entity scoping metadata.

   `ContextPackage` stores `claim_ids`, `memory_ids`, and `retrieved_chunk_ids`
   (`src/personality_jelly/domain/models.py:151`; `src/personality_jelly/storage/orm.py:203`). The
   IDs are globally generated and sufficient today. For P2 inspection, context display may need to
   expand each ID with source work, character, memory scope, and evidence excerpt to avoid manual
   lookups.

## Canon / Memory Boundary Risks

1. Accepted memories are loaded by user-character pair, not by conversation.

   `MemoryRepository.list_for_user_character` filters by `user_id`, `character_id`, optional
   `scope`, and status (`src/personality_jelly/storage/repositories.py:382`). `build_context_package`
   loads all accepted memories for the pair, across conversations
   (`src/personality_jelly/runtime/context.py:61`). That is correct for long-term continuity, but
   P2 needs workspace/user privacy rules before memories can be shared across devices, accounts,
   or imported users.

2. User and relationship memories are persisted with scope, but prompt rendering flattens them.

   `Memory.scope` supports `user_memory`, `relationship_memory`, `session_memory`, and
   `reflective_memory` (`src/personality_jelly/domain/enums.py:29`). The runtime prompt section is
   currently "Accepted User/Relationship Memories" and formats memory contents without showing
   per-memory scope (`src/personality_jelly/runtime/context.py:61`, `:124`). This can make
   relationship memory harder to distinguish from user preference memory in the generated prompt.

3. Memory curation correctly anchors new memory to conversation entities.

   The curator loads the assistant message's context package and conversation, passes
   `interaction_mode` into the guard, and persists memory with `user_id`, `character_id`,
   `conversation_id`, and guarded scope (`src/personality_jelly/memory/curator.py:34`, `:51`, `:52`,
   `:114`, `:124`, `:127`). This is a strong boundary for P2; the remaining risk is presentation
   and review UX, not basic persistence.

4. Layered summaries are deliberately non-canon.

   Context rendering parses summaries into short-term scene state, user memory candidates,
   relationship memory notes, and reflective notes with explicit boundary text
   (`src/personality_jelly/runtime/context.py:92`). Tests verify summary memory candidates are not
   accepted memories and relationship/reflective notes do not rewrite canon/persona context
   (`tests/test_runtime_context.py:319`, `:353`, `:464`).

## CLI Boundary Observations

Ready:

- `demo` and `turn` print `source_work_id`, `character_id`, `persona_version_id`,
  `conversation_id`, and `context_package_id` where relevant
  (`src/personality_jelly/cli/main.py:803`, `:805`, `:806`, `:807`, `:875`, `:876`).
- `show context-package` prints interaction mode, persona version, claim IDs, memory IDs, and
  retrieved chunk IDs (`src/personality_jelly/cli/main.py:1334`, `:1337`, `:1338`, `:1339`,
  `:1340`).
- Eval and retrieval commands print run IDs, character/persona or source-work IDs, case
  interaction modes, context package IDs, expected chunk IDs, and retrieved chunk IDs
  (`src/personality_jelly/cli/main.py:1434`, `:1438`, `:1572`, `:2028`, `:2052`, `:2067`, `:2109`).
- `list memories` requires both `--user-id` and `--character-id`, and prints memory scope
  (`src/personality_jelly/cli/main.py:231`, `:232`, `:1062`).

Hidden or ambiguous:

- `list conversations` is recent-first across all users and characters unless the user uses
  `show conversation`; it prints user and character display names as well as IDs, but there is no
  source-work filter (`src/personality_jelly/storage/repositories.py:327`;
  `src/personality_jelly/cli/main.py:1014`).
- `show character` reports `latest_persona_version_id`, which is useful for inspection but can
  reinforce "latest is active" behavior in automation (`src/personality_jelly/cli/main.py:1289`,
  `:1305`).
- `list claims` hides evidence chunk IDs as noted above.
- There are no first-class CLI commands to list source works or list characters by source work.
  Current workflows discover those IDs mainly through `demo` output or `show character`.

## Areas Already Ready For P2 Expansion

1. Work-scoped data model.

   `SourceChunk`, `Character`, `CanonClaim`, and `PersonaVersion` all preserve `source_work_id`,
   and storage indexes already support work-scoped chunk and character lookup
   (`src/personality_jelly/domain/models.py:43`, `:62`, `:70`, `:98`;
   `src/personality_jelly/storage/orm.py:31`, `:71`).

2. User-character memory partition.

   Memories include `user_id`, `character_id`, optional `conversation_id`, scope, status, reason,
   and importance (`src/personality_jelly/domain/models.py:138`). The repository supports
   user-character-scope-status filtering (`src/personality_jelly/storage/repositories.py:382`).

3. Persona version snapshotting.

   Conversations and context packages store `persona_version_id`, and `create_conversation`
   validates persona ownership before persisting (`src/personality_jelly/runtime/conversation.py:60`;
   `src/personality_jelly/runtime/context.py:75`). This supports repeatable historical inspection.

4. Evidence-backed canon.

   Reader extraction creates claim IDs and evidence refs, validates evidence chunk IDs against
   the selected chunks, and verifier reloads evidence and chunks by those IDs
   (`src/personality_jelly/extraction/reader.py:87`, `:92`;
   `src/personality_jelly/extraction/verifier.py:123`, `:134`).

5. Retrieval evaluation records concrete source evidence refs.

   Retrieval eval cases store expected chunk IDs, retrieved chunk IDs, scores, recall, first
   relevant rank, and missing expected chunk diagnostics
   (`src/personality_jelly/evaluation/retrieval_benchmark.py:47`, `:373`, `:398`, `:489`, `:553`,
   `:597`). This is a good base for work-specific retrieval dashboards.

6. Tests cover important boundary behavior.

   Existing tests check duplicate character rejection in the same work, memory scope separation,
   context package ID persistence, summary non-canon handling, OOC eval persistence, and retrieval
   ranking/empty-result persistence (`tests/test_character_service.py:52`,
   `tests/test_domain_models.py:40`, `tests/test_runtime_context.py:132`,
   `tests/test_runtime_context.py:319`, `tests/test_evaluation_benchmark.py:461`,
   `tests/test_retrieval_benchmark.py:575`).

## Recommended Follow-Up Tasks

1. Add explicit source-work and character discovery surfaces.

   Provide service and CLI/API commands to list source works, list characters within a work, and
   disambiguate same-title works and same-name/same-alias characters. Avoid relying on title/name
   reuse in automation.

2. Require explicit `persona_version_id` in API/service calls that create persistent conversations
   or evaluation runs.

   Keep CLI convenience defaults if useful, but make automation-friendly service boundaries
   deterministic.

3. Introduce a workflow trace context model.

   Add a joinable trace/event context for LLM operations and runtime steps that can carry
   `source_work_id`, `character_id`, `user_id`, `conversation_id`, `message_id`,
   `context_package_id`, `persona_version_id`, and operation name without parsing prompts.

4. Expand context inspection output.

   Add optional verbose expansion for context package claim IDs, memory IDs, memory scopes,
   retrieved chunk source locations, and evidence excerpts. This can stay read-only.

5. Add alias conflict and cross-work identity design.

   Document whether P2 treats same-name characters across works as distinct `Character` rows,
   linked variants, or shared identities with per-work canon bundles. Add alias collision checks or
   diagnostics before multi-character scenes.

6. Separate memory presentation by scope.

   Keep persistence as-is, but render accepted `user_memory` and `relationship_memory` in distinct
   prompt subsections and CLI/API inspection fields so relationship continuity does not blur into
   user preference or canon-adjacent facts.

7. Design multi-character conversation primitives before implementation.

   A future group scene needs participant records, active speaker/target fields, per-character
   persona selection, and per-message author semantics. The current one-character `Conversation`
   should remain stable until that model is explicit.

## Verification

No automated tests were required or run for this audit because the task changed documentation only.
