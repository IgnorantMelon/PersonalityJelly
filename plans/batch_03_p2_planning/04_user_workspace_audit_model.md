# User / Workspace / Audit Concept Design

This is a P2 concept design for the minimum user, workspace, and audit concepts needed before
service/API work. It is planning only: no schema, migration, auth, permission, or platform-layer
changes are proposed for this batch.

This plan uses the Task 02 draft report from
`origin/planning/multi-entity-boundary-audit` at
`e452340ffe0b23b704f3d1cee07d75b6efde9373`, which identified that most core IDs are already
preserved, while P2 risks cluster around ambiguous latest/default selection, missing joinable LLM
trace context, and memory scope presentation.

## Recommendation Summary

- Keep `User` minimal for early P2. Treat it as a local continuity subject, not an account.
- Do not introduce `Workspace` as a required early P2 runtime model. Keep it as a later platform
  concept, while reserving ownership rules so future workspace scoping can be added cleanly.
- Add an audit concept before exposing API write workflows or richer manual review tools. The
  minimum audit unit should be a structured workflow/event record that links actor, action,
  affected entity, reason, semantic trace IDs, and before/after state where practical.
- Preserve strict canon and memory boundaries. Audit data can explain or review changes, but it
  must not become canon, persona, or accepted memory by itself.

## Minimum User Concept

The current `User` model has only `id`, optional `display_name`, and `created_at`. That is enough
for the local MVP because user identity currently exists to partition conversations and long-term
memory:

- `Conversation.user_id` binds dialogue continuity to one user-character-persona path.
- `Memory.user_id` and `Memory.character_id` partition accepted user and relationship memories.
- `create_user` allows explicit `user_id`, which is useful for deterministic tests, imports, and
  future service callers.

Early P2 should define `user` as:

- a local continuity identity;
- the owner of private user memory for a character;
- one side of a user-character relationship memory boundary;
- the actor for manual review or API writes when a real authenticated actor model does not yet
  exist.

Early P2 should not define `user` as:

- an authenticated account;
- a billing or quota subject;
- a permission principal across tenants;
- a namespace for source works or characters;
- a replacement for future workspace membership.

Recommended early P2 rules:

- Service/API write requests that affect conversations or memories should require an explicit
  `user_id`, except for clearly marked local/demo helpers.
- Do not resolve users by `display_name` in service/API workflows. The CLI demo may keep
  display-name reuse as a convenience, but service calls should use IDs.
- Memory inspection and review should always show `user_id`, `character_id`, `scope`, `status`,
  and `conversation_id` when present.
- A synthetic or local actor ID such as `system`, `cli`, or `api-local` can be used in audit events
  until an authenticated actor model exists.

## Workspace Timing

Do not add a workspace model in early P2.

The current product is still a local, CLI-first character brain. Source works, characters, persona
versions, conversations, memories, traces, and evaluation runs already carry enough IDs for local
inspection and service extraction. Adding `workspace_id` now would force schema and permission
decisions before the project has settled multi-work, multi-character, and API boundaries.

Workspace should remain a later platform concept used for:

- grouping source works, characters, users, conversations, and evaluations for a project or tenant;
- permission checks and membership;
- separating private user data between teams or deployments;
- API key, audit retention, and operational policy.

Early P2 should prepare for workspace later by:

- avoiding global name-based service selection;
- requiring explicit IDs in durable service/API writes;
- keeping source work, character, persona, user, conversation, and eval ownership fields visible in
  responses;
- designing audit events with optional future `workspace_id`, but not requiring it now.

## Audit Log Minimum Requirements

The first audit concept should be structured, append-only, and entity-linked. It should support
manual review and future API write operations without becoming a full compliance system.

Minimum audit event fields:

- `id`
- `created_at`
- `actor_type`: `system`, `cli_user`, `api_user`, `provider`, or future `workspace_member`
- `actor_id`: local user ID, synthetic actor label, provider name, or future account/member ID
- `operation`: stable action name such as `memory.review`, `memory.edit`, `canon_claim.review`,
  `conversation.turn`, or `benchmark.review`
- `entity_type` and `entity_id`
- optional related IDs: `source_work_id`, `character_id`, `user_id`, `conversation_id`,
  `message_id`, `context_package_id`, `persona_version_id`, `critic_report_id`,
  `llm_trace_id`, `evaluation_run_id`
- `reason`: required for human/manual changes
- `before`: compact structured snapshot or selected fields before the change
- `after`: compact structured snapshot or selected fields after the change
- `metadata`: small structured data for workflow-specific context

Minimum audit behavior:

- Write one audit event per manual semantic-state mutation.
- Link provider-driven semantic decisions to persisted `LLMRawOutput` records when available.
- Record rejected or failed semantic writes too, especially when a guard/critic decision prevents a
  memory from becoming accepted.
- Keep audit events read-only after creation.
- Do not use audit events as business state. Domain models remain the source of current state.

Audit can start as an application-service concept before a physical audit table exists. For the
first implementation batch, it is acceptable to define event payload models and record them only
when a persistence target is introduced.

## Required Audit Coverage

Manual memory review/edit/archive:

- Required before exposing these operations through API or richer UI.
- Current repository methods require review/edit reasons for review and edit, but archive only
  changes status. Audit should require a reason for archive too.
- Audit should record memory `scope`, `status`, `content`, `reason`, `user_id`, `character_id`,
  and `conversation_id`.

Canon claim review or correction:

- Required before adding human claim correction workflows.
- Verifier already records structured provider output through `LLMRawOutput`; human review should
  add an audit event with before/after status, confidence, reasoning, and affected evidence refs.
- Canon changes must remain evidence-backed. A human correction can mark review state or reasoning,
  but new verified canon should still reference source evidence or explicit human-review policy.

Provider/model calls that affect semantic state:

- Required for provider calls that can create or mutate canon, persona, memory, mode, critic,
  benchmark, or retrieval evaluation state.
- Existing `LLMRawOutput` records operation, schema, provider, model, raw output, parsed output,
  and validation errors. The missing P2 piece is joinable workflow context: related entity IDs and
  the workflow step that consumed the trace.
- Early P2 can bridge this with audit events that include `llm_trace_id` and related IDs, without
  changing every trace row immediately.

Benchmark or failure-case review:

- Required before manual triage can change benchmark/failure-case status, severity, or disposition.
- Existing failure cases and evaluation runs are good immutable records of what happened. Audit
  should record review notes, export/curation decisions, and whether a failed case was promoted to
  a regression cases file.

Future API write operations:

- Required for any API operation that mutates durable state: source ingest, character create,
  conversation create, turn run, memory review/edit/archive, claim review, persona compile, and
  benchmark run/review.
- API handlers should pass an actor context and request ID into application services so audit
  events can be written outside HTTP-specific code.

## Ownership Boundaries

| Entity | Current owner / scope | P2 rule | Can wait |
| --- | --- | --- | --- |
| Source works | Currently global local records with title/author/language/source type. | Require explicit `source_work_id` for downstream workflows; do not select by title in service/API writes. | Workspace/project ownership. |
| Source chunks | Owned by `source_work_id`. | Keep chunk IDs source-backed and inspectable through evidence/retrieval outputs. | Cross-work source bundles. |
| Characters | Owned by one source work through `source_work_id`. | Treat same-name characters in different works as distinct until identity-link design exists. | Shared character identity across works. |
| Canon claims | Owned by `source_work_id` and `character_id`. | Canon updates must stay evidence-backed or explicitly human-reviewed and audited. | Cross-work canon policies. |
| Evidence refs | Owned by claim and source chunk. | Preserve `chunk_id` and excerpt in inspection/audit for claim review. | Evidence graph beyond source chunks. |
| Persona versions | Owned by `character_id` and `source_work_id`; conversations snapshot `persona_version_id`. | Durable service/API workflows should use explicit `persona_version_id`. | Global persona release channels. |
| Users | Local continuity identity. | Own private memory and conversations; not an auth account. | Account login, external identity, membership. |
| Conversations | Owned by one `user_id`, one `character_id`, and one `persona_version_id`. | Keep one-character conversation model for P2 service extraction. | Multi-character/group conversations. |
| Messages | Owned by conversation. | Preserve role, content, context package linkage for turn audit. | Per-message visibility policy. |
| User memory | Owned by `user_id` + `character_id`, optionally linked to `conversation_id`. | Private to that user-character pair; never canon. Manual mutation must be audited. | Sharing memory across users/devices/workspaces. |
| Relationship memory | Owned by the same user-character pair, distinguished by `Memory.scope`. | Relationship continuity only; must not rewrite original character relationships or canon. | Relationship memory between multiple fictional characters. |
| Context packages | Owned by conversation and persona version, with claim/memory/chunk ID arrays. | Treat as runtime evidence snapshots. They are inspectable but not user memory or canon. | Prompt redaction/permission policy. |
| Critic reports | Owned by assistant message. | Treat as quality review outputs that may create failure cases, not as direct state mutation. | Human critic adjudication workflow. |
| Failure cases | Owned by conversation and linked messages/context/critic report. | Use for review and regression capture; manual triage requires audit. | Full issue tracker semantics. |
| LLM traces | Currently operation/provider/model-scoped. | Link via audit/workflow context when the trace affects semantic state. | First-class trace foreign keys on every row. |
| OOC evaluation runs | Owned by `character_id` and `persona_version_id`. | Use for quality diagnostics only; results must not rewrite canon/persona/memory directly. | Source-work field and workspace dashboards. |
| Retrieval evaluation runs | Owned by `source_work_id` and `character_id`. | Keep expected/retrieved chunk IDs visible for retrieval review. | Multi-work retrieval runs. |

## Required For P2

These ownership and audit rules should be required before API write workflows are implemented:

- Explicit ID-based service/API writes for source work, character, persona version, user, and
  conversation selection.
- Actor context for write services, even if actor is `cli` or `local_user` for now.
- Audit events for manual memory review/edit/archive.
- Audit events for human canon claim review/correction.
- Linkable workflow context for provider calls that affect semantic state, at least through audit
  events referencing `LLMRawOutput` IDs.
- Separate response fields for user memory and relationship memory scopes in inspection surfaces.
- Audit or workflow records for benchmark/failure-case review decisions.

## Can Wait Beyond P2

These are intentionally deferred:

- Workspace table, membership, roles, and permission checks.
- Authentication, account linking, API keys, quotas, billing, or multi-tenant isolation.
- Full immutable event sourcing of every domain state transition.
- Cross-work character identity graph or shared canon bundles.
- Multi-character conversation participant model.
- Fine-grained prompt redaction based on viewer permissions.
- Audit retention, export, legal/compliance reporting, or admin dashboards.
- Provider cost accounting and rate-limit policy.

## Implementation Notes For Later

When implementation begins, avoid adding audit logic inside CLI print functions or future HTTP
handlers. Audit should live in application services that already know actor context, session,
selected entities, and workflow result.

Use deterministic validation for ownership checks:

- `persona_version_id` belongs to `character_id`;
- `character_id` belongs to `source_work_id` when both are provided;
- `conversation_id` belongs to the expected `user_id` and `character_id`;
- memory review/edit/archive preserves `user_id`, `character_id`, and `scope`;
- claim review preserves source work, character, and evidence linkage.

Do not add semantic keyword checks for audit decisions. Audit records should capture structured
outputs from existing semantic judges and human reasons, not re-judge content in a new layer.

## Verification

No automated tests were required or run because this task changed documentation only.
