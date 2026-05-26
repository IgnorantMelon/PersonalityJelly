# Task 03: API Redaction Policy

Batch 06 is a planning/readiness batch. This document defines the future API
redaction and exposure contract only; it does not implement redaction code,
change current Batch 05 route fields, add auth, add write routes, or change
semantic safety behavior.

## Current State

- Batch 05 exposes a local read-only FastAPI adapter over
  `personality_jelly.application` inspection services.
- Route handlers in `personality_jelly.api.routes` return application
  inspection models directly. There is no API-specific redaction layer today.
- The current API is local and inspection-oriented. It intentionally exposes
  several large or sensitive fields that are useful for debugging:
  `ContextPackageDetail.assembled_prompt`, message `content`, memory
  `content` and `reason`, source chunk text, LLM trace `raw_output`,
  trace `parsed_output`, trace `validation_errors`, benchmark prompts/queries,
  and nested failure-case messages.
- `src/personality_jelly/storage/models.py` does not exist in the current tree.
  Durable schema is represented by `src/personality_jelly/storage/orm.py`;
  domain data shapes are represented by `src/personality_jelly/domain/models.py`.
- Health responses already avoid local database URLs, paths, provider config,
  and secrets. CLI config commands may show local config paths and base URLs,
  but this policy is for HTTP API exposure.
- Task 01 keeps API handlers thin and defers write routes. Task 02 defines
  local actor context and payload-only audit readiness while deferring full
  auth/platform roles. Task 04 defines future pagination/filter conventions but
  preserves Batch 05 compatibility until a coordinated migration.

## Redaction Profiles

Future implementation should use explicit response profiles instead of
per-route ad hoc field suppression.

| Profile | Intended use | Contract |
| --- | --- | --- |
| `local_mvp_compat` | Current Batch 05 local-only read API behavior. | May keep existing raw inspection fields for compatibility. Do not add broader exposure to new routes by copying this profile. |
| `local_default` | Recommended default for new local API clients after redaction implementation. | Exposes IDs, counts, statuses, timestamps, risk labels, and compact previews where useful. Redacts raw prompts, raw user text, full memories, full source chunks, full trace payloads, and stack traces unless a route is explicitly local-debug. |
| `local_debug` | Explicit local diagnostics requested by an operator. | May expose raw prompts, messages, memories, source chunks, trace payloads, validation payloads, provider/model labels, and benchmark cases for targeted debugging. It still never exposes secrets, auth headers, API keys, raw provider config, or unredacted stack traces in HTTP responses. |
| `platform_default` | Future broad or hosted clients before precise ownership/role policy exists. | Most restrictive default. Exposes durable IDs, relationship IDs only when allowed by the future actor/auth contract, counts, statuses, timestamps, aggregate metrics, and redaction metadata. Raw text and diagnostic payloads are omitted or replaced with redaction markers. |
| `platform_privileged_debug` | Future admin/debug surface after platform auth exists. | Requires an accepted auth/role policy outside this task. It may resemble `local_debug` for authorized diagnostics, but secrets remain never-expose and raw user text requires explicit ownership/support policy. |

Implementation batches should not silently choose `local_mvp_compat` for new
write-era routes. The safe next default is `local_default`.

## Sensitive API-Visible Inventory

This inventory describes the sensitive data families currently visible through
read-only inspection models or likely to become visible through future write
responses.

| Family | Current persisted/application fields | Current API visibility | Sensitivity |
| --- | --- | --- | --- |
| Assembled prompts and context packages | `ContextPackage.assembled_prompt`, `claim_ids`, `memory_ids`, `retrieved_chunk_ids`, interaction mode, persona version ID. | `GET /context-packages/{context_package_id}` returns `assembled_prompt` by default and can expand claims, memories, retrieved chunks, and retrieved chunk text. | Combines system instructions, persona, verified claims, accepted memories, retrieved source chunks, conversation summary, and current user message. Treat as high sensitivity. |
| Raw user and assistant messages | `Message.content`, role, conversation ID, context package ID. | Conversation detail returns recent messages by default; critic/failure/eval detail can include nested messages. | User text can contain private data. Assistant text can quote user text, memory, prompt context, or source. Treat both as high sensitivity. |
| User and relationship memories | `Memory.content`, `reason`, `scope`, `status`, ownership IDs, importance. | Memory list/detail expose content and reason; conversation/context expansion can include memories. | Personal continuity and relationship state. High sensitivity, especially accepted memories. |
| Conversation summaries and layered summary fields | `Conversation.summary`, parsed `summary_layers`: short-term scene state, user memory candidates, relationship memory notes, reflective notes. | Conversation list/detail expose raw summary and parsed layers. | May contain raw user facts, relationship notes, and reflective operational notes. High sensitivity for platform defaults. |
| Source chunks and evidence snippets | `SourceChunk.text`, `text_preview`, chapter/paragraph/char offsets; `EvidenceRef.excerpt`; claim `content` and `reasoning`. | Source chunk detail exposes full text. Character/claim routes expose claim content, evidence excerpts, and chunk previews. Context/retrieval expansion can expose chunk previews or full retrieved chunk text. | Source text may be copyrighted, private, or user-supplied. Evidence snippets and claim reasoning can reveal source text. Medium to high sensitivity depending on client. |
| Persona fields and verified canon | `PersonaVersion.core_self`, speech rules, behavior rules, world adaptation rules, forbidden rules, `source_claim_ids`; claim summaries. | Character detail exposes latest persona `core_self` and claims; context prompt embeds full persona rules internally. | Less private than user memory, but may reveal source-derived canon and prompt-shaping rules. Medium sensitivity, high when embedded in assembled prompts. |
| Raw LLM output and parsed structured output | `LLMRawOutput.raw_output`, `parsed_output`, `response_schema`, `validation_errors`. | Trace detail exposes all of these fields. Trace list exposes operation, schema, provider, model, validation error count. | Raw provider payloads and parsed outputs can include prompts, user text, source text, memories, model refusals, or malformed content. High sensitivity. |
| Provider/model labels and trace metadata | `LLMRawOutput.provider_name`, `model_name`, `operation`, `schema_name`, timestamps; retrieval run `embedding_model`. | Trace list/detail and retrieval run summaries expose provider/model labels. | Provider/model labels are acceptable for local diagnostics but can reveal infrastructure or cost strategy. Medium sensitivity; platform defaults should prefer aliases. |
| Provider config and secrets | `Settings` has database URL, config file, provider names, base URLs, models, timeouts, API keys; `OpenAICompatibleConfig` has `base_url`, `api_key`, auth headers. | Batch 05 health does not expose these. CLI config show/check exposes base URLs and booleans, not key values. | Secrets and auth headers are never-expose. Base URLs, database URLs, local config paths, and config file names are sensitive in HTTP. |
| Critic reports and failure cases | `CriticReport.reasons`, risk labels, suggested action; `FailureCase.reason`, `notes`, linked messages/context/critic. | Critic detail exposes reasons and nested message. Failure detail exposes reason, notes, nested user/assistant messages, context summary, and critic summary. | Reasons/notes can quote sensitive text or model analysis. High sensitivity when nested messages are included. |
| OOC benchmark cases and outputs | `EvaluationCaseResult.prompt`, status, reasons, assistant message ID, critic report ID, nested assistant message. | Eval run detail exposes case prompts, reasons, nested assistant message, conversation ID, context package ID. | Prompts and outputs may contain user/source text and diagnostic adversarial cases. High sensitivity outside local debug. |
| Retrieval benchmark cases and outputs | `RetrievalEvaluationCaseResult.query`, expected/retrieved chunk IDs, scores, reasons, diagnostics, chunk previews when included. | Retrieval eval detail exposes query, IDs, scores, reasons, and chunk summaries by default via `include_chunks=true`. | Queries can contain raw user/source text. Chunk previews reveal source. Medium to high sensitivity. |
| Error responses and stack traces | API error envelope includes code, message, details, optional trace ID; `normalize_error` currently uses `str(error)` for unexpected errors. | Unexpected errors can return exception text and exception type. No stack traces are currently returned by the shared handler. | Exception messages can contain paths, SQL URLs, provider body text, or payload fragments. Stack traces are never-expose in HTTP. |

## Field-Level Default Exposure

The tables below define the target exposure for later implementation. They do
not require changing Batch 05 fields in this planning branch.

### Common Low-Sensitivity Fields

| Field family | Local MVP compatibility | Future local debug | Future platform default |
| --- | --- | --- | --- |
| Durable entity IDs | Expose. | Expose. | Expose only within authorized resource scope once platform auth exists; otherwise expose only IDs needed by the route. |
| Timestamps | Expose. | Expose. | Expose. |
| Counts and aggregate metrics | Expose. | Expose. | Expose. |
| Enum/status/risk labels | Expose. | Expose. | Expose unless the label itself reveals unsupported governance state. |
| Relationship IDs such as `user_id`, `character_id`, `conversation_id` | Expose as today. | Expose. | Expose only under the future actor/auth ownership contract. Hosted broad diagnostic lists should avoid cross-user IDs by default. |

### Conversation, Message, Memory, And Context Fields

| Field | Local MVP compatibility | Future local debug | Future platform default |
| --- | --- | --- | --- |
| `Conversation.summary` | Expose as today. | Expose full. | Redact by default. Return `summary_present`, `summary_length`, optional layer availability, and a redaction marker. |
| `Conversation.summary_layers.short_term_scene_state` | Expose as today. | Expose full. | Redact by default unless an owner-visible conversation surface explicitly allows it. |
| `summary_layers.user_memory_candidates` | Expose as today. | Expose full. | Redact by default. These are unreviewed memory candidates. |
| `summary_layers.relationship_memory_notes` | Expose as today. | Expose full. | Redact by default. |
| `summary_layers.reflective_notes` | Expose as today. | Expose full for diagnostics. | Redact by default. Operational notes should not leak into broad clients. |
| `Message.content` for user messages | Expose as today. | Expose full. | Redact by default. Future owner-facing conversation routes may expose only after auth/ownership is accepted. |
| `Message.content` for assistant messages | Expose as today. | Expose full. | Redact by default for diagnostics because assistant text can quote user/source/memory data. |
| `Memory.content` | Expose as today on memory endpoints and expansions. | Expose full. | Redact by default. Return ID, scope, status, importance, created_at, and `content_redacted=true`. |
| `Memory.reason` | Expose as today. | Expose full. | Redact by default. It may include user text or model reasoning. |
| `ContextPackage.assembled_prompt` | Expose as today. | Expose full only under explicit debug profile. | Always omit or replace with `[redacted:assembled_prompt]` by default. Return `assembled_prompt_redacted=true`, length/hash if useful, and linked IDs. |
| `ContextPackage.claim_ids`, `memory_ids`, `retrieved_chunk_ids` | Expose as today. | Expose. | Expose only within authorized scope; otherwise aggregate counts. |
| Context package expanded memories | Expose as today. | Expose full. | Use redacted `MemorySummary` shape. Include IDs/counts only by default. |
| Context package expanded retrieved chunks | Expose previews/full text according to current flags. | Expose previews/full text when debug asks. | IDs and counts by default. No full text. Previews require a source-access policy. |

### Source, Claim, Persona, And Evidence Fields

| Field | Local MVP compatibility | Future local debug | Future platform default |
| --- | --- | --- | --- |
| `SourceWork.title`, `author`, `language`, `source_type` | Expose as today. | Expose. | Expose only within source-work scope. Titles/authors may be visible in owner/admin views, but not broad global lists. |
| `SourceChunk.text` | Expose as today on detail route. | Expose full for source debugging. | Redact by default. Return location metadata and `text_redacted=true`. |
| `SourceChunk.text_preview` | Expose as today. | Expose. | Redact by default unless a future source-access contract allows previews. |
| `EvidenceRef.excerpt` | Expose as today. | Expose. | Redact by default or replace with excerpt length and source chunk ID. |
| `CanonClaim.content` | Expose as today. | Expose. | Usually expose only in character/canon owner/admin surfaces. Broad diagnostic defaults may return claim IDs, type, status, confidence, and evidence count without content. |
| `CanonClaim.reasoning` | Expose as today. | Expose. | Redact by default. It can quote source or verifier details. |
| `PersonaVersion.core_self` | Expose as today in summaries. | Expose. | Redact by default for diagnostic lists. Owner/admin character surfaces may expose accepted persona summaries after auth policy exists. |
| Persona rules embedded in prompts | Not directly exposed except through `assembled_prompt`. | Expose only through explicit prompt debug. | Never exposed through default API responses. |

### Trace, Provider, Critic, Failure, And Benchmark Fields

| Field | Local MVP compatibility | Future local debug | Future platform default |
| --- | --- | --- | --- |
| Trace `operation`, `schema_name`, `validation_error_count`, `created_at` | Expose as today. | Expose. | Expose. These are safe diagnostic selectors. |
| Trace `provider_name`, `model_name`, retrieval `embedding_model` | Expose as today. | Expose labels. | Redact or map to configured aliases by default. Do not expose base URLs or deployment-specific model names without a platform debug policy. |
| Trace `response_schema` | Expose as today on detail route. | Expose for schema/debug. | Redact by default. Schema can reveal prompt strategy and structured extraction targets. |
| Trace `raw_output` | Expose as today on detail route. | Expose full only in debug. | Redact by default. |
| Trace `parsed_output` | Expose as today on detail route. | Expose full only in debug. | Redact by default. A compact `parsed_output_present` or known-safe result summary is acceptable. |
| Trace `validation_errors` | Expose as today. | Expose full only in debug after recursive secret/path scrubbing. | Redact by default. Return count and normalized error families only. |
| Critic risk labels and suggested action | Expose as today. | Expose. | Expose. These are compact diagnostic labels. |
| Critic `reasons` | Expose as today. | Expose. | Redact by default or return sanitized reason categories only. Reasons can quote messages or canon. |
| Failure case category and linked IDs | Expose as today. | Expose. | Expose within authorized scope. |
| Failure case `reason`, `notes` | Expose as today. | Expose. | Redact by default. |
| Failure case nested messages/context/critic | Expose as today. | Expose according to debug profile. | Redact nested raw fields recursively. |
| OOC eval run aggregates | Expose as today. | Expose. | Expose. |
| OOC eval case `prompt` | Expose as today. | Expose. | Redact by default. |
| OOC eval case `reasons` | Expose as today. | Expose. | Redact by default or return normalized failure categories. |
| OOC eval nested assistant message | Expose as today. | Expose. | Redact by default. |
| Retrieval eval run aggregates and scores | Expose as today. | Expose. | Expose aggregate metrics and scores. |
| Retrieval eval case `query` | Expose as today. | Expose. | Redact by default. |
| Retrieval eval expected/retrieved chunk IDs | Expose as today. | Expose. | Expose only within authorized source scope; otherwise counts and top-rank indicators. |
| Retrieval eval chunk previews | Expose as today when `include_chunks=true`. | Expose under debug/source access. | Redact by default. |

## Redaction Behavior Rules

### Never-Expose Data

These values must never appear in HTTP responses under any profile:

- API keys and bearer tokens.
- Auth headers, cookies, request signing material, OAuth/session tokens, and
  future service tokens.
- Environment variable values such as `PJ_LLM_API_KEY` and
  `PJ_EMBEDDING_API_KEY`.
- Raw provider config objects that include secrets.
- Database URLs or provider URLs with embedded credentials.
- Full Python stack traces in response bodies.

Recommended replacement markers:

- `[redacted:secret]`
- `[redacted:auth_header]`
- `[redacted:stack_trace]`
- `[redacted:database_url]`

Boolean indicators such as `api_key_configured=true` are acceptable.

### Provider Config And Model Labels

- Current stored trace labels `provider_name` and `model_name` are acceptable in
  local compatibility and local debug profiles.
- Future platform defaults should expose only `provider_alias`,
  `model_alias`, or `model_name_redacted=true` unless a platform debug role is
  accepted.
- Provider base URLs, deployment URLs, organization IDs, project IDs, request
  headers, retry config with headers, and raw provider config dictionaries are
  redacted by default and omitted from platform responses.
- Local debug may expose a sanitized provider endpoint label only when it strips
  credentials, query strings, fragments, and local network details. Secrets
  remain never-expose.

### Local Filesystem Paths

- API responses should not expose local filesystem paths by default.
- Redact paths in database URLs, config file paths, source ingest paths,
  exception messages, validation errors, and provider/tool errors.
- Prefer returning `path_redacted=true`, a stable resource ID, and the operation
  that failed.
- Local debug may expose a basename or path kind (`database`, `config_file`,
  `source_input`) only when useful. Full absolute paths should stay out of HTTP
  responses unless a future local-only debug endpoint explicitly accepts that
  risk.

### Raw Prompts And Prompt-Like Payloads

Treat these as prompt-like and redact by default outside explicit local debug:

- `ContextPackage.assembled_prompt`.
- Any system/developer/assistant/user chat messages sent to a provider.
- JSON-schema compatibility instructions injected into prompts.
- Retrieved chunks embedded in prompt sections.
- Persona rules, claim contents, memory contents, summaries, and current user
  message when present inside an assembled prompt.
- Raw provider request payloads if they are stored in future trace tables.

Default response should return:

- `assembled_prompt_redacted=true`;
- optional `assembled_prompt_length`;
- optional `assembled_prompt_hash` if useful for correlation;
- linked IDs and section counts.

### Raw User Text

Raw user text includes message content, memory content, conversation summary
fragments that came from the user, eval prompts/queries derived from user text,
and trace payload fragments. Default platform responses should redact it until
ownership and support-role policy exists.

Recommended replacement:

```json
{
  "content": "[redacted:user_text]",
  "content_redacted": true
}
```

For local debug, expose raw user text only when a caller explicitly requests the
debug profile for a targeted resource. Do not expose raw user text through broad
list endpoints by default.

### Source Text

Source text includes full chunks, previews, evidence excerpts, and benchmark
source snippets. It is not always private user text, but it can be copyrighted,
private, or user-supplied. Platform defaults should return IDs, location
metadata, and counts. Previews or full chunks require a future source-access
contract.

### Stack Traces And Error Messages

- Default API errors should use stable `code`, generic `message`, sanitized
  `details`, and optional `trace_id`.
- Do not return stack traces in any HTTP profile.
- Do not return raw exception text for unexpected errors until it passes a
  sanitizer that removes secrets, paths, URLs, prompt fragments, provider body
  text, SQL statements, and user text.
- Future local debug should correlate to logs through `trace_id`,
  `request_id`, or `workflow_id` instead of embedding full traceback text in the
  JSON response.

## Placement Recommendation

Redaction should live in a shared serializer layer, not in repositories and not
as scattered route-level field edits.

Recommended layering:

1. Domain and storage models keep complete persisted values. Do not mutate or
   partially store redacted values in durable records.
2. Application inspection services may continue to assemble complete
   transport-neutral inspection models for CLI and explicit debug use.
3. Add an application-level redaction/serialization module, for example
   `personality_jelly.application.redaction`, with:
   - a `RedactionProfile` enum;
   - policy tables for inspection model families;
   - recursive sanitizers for nested dict/list payloads;
   - helpers that convert complete inspection results into safe response
     models or safe dictionaries.
4. API route handlers remain thin. They select or receive the redaction profile
   from request context/dependencies, call application inspection services, pass
   the result through the redaction serializer, and return typed response
   models.
5. API response models should enforce the default shape. A default platform
   response model should not contain fields such as `raw_output`,
   `assembled_prompt`, `MessageSummary.content`, or `SourceChunkDetail.text` at
   all unless the route/profile explicitly supports them.
6. Future audit event listing and write responses should reuse the same
   redaction helpers before returning `before`, `after`, `metadata`, provider
   failure details, or partial workflow diagnostics.

Why not only API response models:

- Pydantic models can prevent accidental fields in route responses, but they do
  not solve nested dict redaction for `parsed_output`, validation errors, audit
  metadata, or future provider payloads.

Why not only application inspection services:

- CLI and local debugging still need complete inspection output. Redacting at
  the source would make local debugging worse and could encourage bypass routes.

The implementation should combine both: shared redaction serializer for policy
and strict API models for default response schemas.

## Compatibility Guidance For Existing Batch 05 Routes

Do not change current Batch 05 route fields in this planning task. A later
implementation batch should migrate in a coordinated pass:

1. Add redaction profiles and serializer helpers without changing route
   behavior.
2. Add tests that prove `local_mvp_compat` reproduces current Batch 05 fields.
3. Add `local_default` safe schemas for new routes first.
4. Migrate existing read-only routes route-family by route-family, updating API
   contract tests and documenting compatibility changes.
5. Keep explicit local debug access for context packages, trace details, source
   chunks, eval cases, and failure cases so CLI/API debugging remains possible.

Existing include flags such as `include_memories`, `include_retrieved_chunks`,
`include_retrieved_chunk_text`, `failed_only`, and `include_chunks` should not
override redaction. They should control expansion within the active redaction
profile.

## Future Write Response Guidance

Future write routes from Task 01 should avoid returning raw text by default.

- Source ingest responses: return source work ID, chunk count, source metadata,
  and redaction metadata. Do not echo full ingested text by default.
- Conversation creation: return IDs and conversation summary fields with no raw
  messages.
- Turn execution: default response should include user/assistant message IDs,
  context package ID, status, warnings, critic/failure/memory IDs, and redacted
  text markers. Full prompt/message output is local debug only.
- Summary generation: return summary status and layer availability by default;
  raw summary text requires local debug or future owner-visible policy.
- Manual memory review/edit/archive: return updated memory identity, scope,
  status, importance, and audit payload with memory content/reason redacted by
  default unless explicitly local debug.
- Benchmark execution: return run ID, status, counts, diagnostics, and case IDs
  by default. Case prompts, queries, messages, and chunks are debug-only.
- Provider-backed partial results: include persisted IDs, failed step, sanitized
  error family, and retry hint. Do not include raw provider payloads or prompts.

## Audit Response Guidance

Task 02's audit payloads can contain before/after memory snapshots today.
Before audit events are exposed through HTTP:

- `actor.actor_id` is local attribution, not authentication proof. Platform
  defaults may need to redact or alias actor IDs.
- `reason` may be caller-provided and can include sensitive text. Redact by
  default in platform surfaces.
- `before` and `after` snapshots must use the same field-level redaction as the
  target entity. Memory content and reason are not safe just because they are
  inside audit payloads.
- `metadata` needs recursive key and value sanitization. It must not contain
  prompts, raw provider outputs, local paths, stack traces, secrets, auth
  headers, or raw provider config.
- `related_ids` can be exposed within authorized resource scope; broad
  diagnostics should use counts or filtered views.

## Future Implementation Tests

Later implementation should add focused tests before switching default API
profiles.

### Policy And Serializer Unit Tests

- Redaction recursively removes keys named or ending with `api_key`, `token`,
  `secret`, `password`, `authorization`, `cookie`, `auth_header`, and similar
  secret-bearing names from nested dict/list payloads.
- Secret values are replaced by stable markers and never by partial secret
  substrings.
- Database URLs and provider URLs with credentials are redacted.
- Absolute Windows and POSIX paths in error strings are replaced with a path
  marker.
- `local_debug` still redacts secrets and auth headers.
- `local_default` and `platform_default` redact prompt-like, user-text,
  source-text, and trace-payload fields according to this document.
- Hash/length metadata for redacted prompts is deterministic if implemented.

### Route Tests For Current Read-Only Families

- Default context package response does not contain `assembled_prompt`.
- Default context package response does not expose memory content or retrieved
  chunk text even when expansion flags are true.
- Default conversation detail does not expose `messages[].content`,
  `memories[].content`, memory `reason`, or raw summary layers.
- Default memory list/detail does not expose memory content or reason.
- Default source chunk detail does not expose `text` and does not expose
  `text_preview` unless the active profile allows previews.
- Default claim/character responses redact evidence excerpts, claim reasoning,
  and chunk previews where policy requires.
- Default critic/failure responses redact `reasons`, `notes`, nested message
  content, and nested context prompt fields while preserving IDs and risk
  labels.
- Default trace detail does not expose `raw_output`, `parsed_output`,
  `response_schema`, or raw `validation_errors`; it returns validation error
  count and sanitized families only.
- Default eval run detail does not expose case `prompt`, nested assistant
  message content, or raw reasons.
- Default retrieval eval detail does not expose case `query` or chunk previews;
  aggregate diagnostics and scores remain visible.
- Existing list filters and pagination behavior remain compatible with Task 04
  until an intentional route-contract migration changes them.

### Debug Profile Tests

- Explicit local debug profile can return assembled prompts, raw trace payloads,
  source chunk text, benchmark prompts/queries, messages, and memories for a
  targeted resource.
- Debug profile cannot be activated accidentally by include flags alone.
- Debug profile still redacts API keys, auth headers, token-looking fields,
  database credentials, and stack traces.
- Debug profile response schemas or OpenAPI naming make broad exposure obvious
  to client authors.

### Error And Provider Failure Tests

- Unexpected exception responses do not include absolute paths, SQL statements,
  database URLs, provider base URLs, raw provider response bodies, prompts, or
  stack traces.
- Provider failure responses include sanitized error family and trace/workflow
  IDs when available, not raw payloads.
- Validation errors that reference trace payloads or user content are summarized
  safely in default profiles.
- Future write route partial responses include persisted IDs and failed step
  without raw prompts/messages.

### Audit Tests

- Audit payloads returned by manual memory workflows redact memory content and
  reason in default API responses.
- Audit metadata recursively redacts secrets, provider config, local paths, raw
  prompts, raw provider output, and stack traces.
- Actor IDs and related IDs follow the accepted actor/auth policy before
  platform exposure.
- Audit persistence, when added, stores complete records but API reads apply
  redaction before serialization.

### Contract Tests

- Default OpenAPI schemas for broad/platform-safe routes do not include
  `assembled_prompt`, `raw_output`, `parsed_output`, `MessageSummary.content`,
  `SourceChunkDetail.text`, or memory `content`.
- Compatibility tests prove `local_mvp_compat` output still matches current
  Batch 05 responses until the coordinated migration intentionally changes it.
- Snapshot tests should include nested failure/eval/trace examples because most
  leaks occur through nested linked models rather than top-level fields.

## Implementation Prerequisites

Before making `platform_default` or `local_default` the default for existing
read routes:

1. Decide how API clients request `local_debug` without adding production auth.
   For local-only use, this can be an explicit app setting or query/dependency
   flag, but it must not be silently enabled by include flags.
2. Add redacted response models or safe dict serializers for every inspection
   family named above.
3. Add recursive sanitization for arbitrary dict/list payloads before exposing
   trace parsed output, validation errors, provider error bodies, audit
   metadata, or future write partial details.
4. Add route tests and contract tests before changing defaults.
5. Coordinate with Task 05 so error responses, trace IDs, request IDs, and
   workflow IDs let local operators debug without embedding raw stack traces or
   payloads in HTTP responses.

## Explicit Non-Goals

- No redaction code in Batch 06 Task 03.
- No source, test, README, or VIBE changes in this task.
- No removal of current Batch 05 route fields in this planning branch.
- No auth, roles, permissions, API keys, sessions, workspaces, CORS, server
  deployment, or write routes.
- No changes to canon, memory, retrieval, critic, benchmark, or semantic safety
  rules.
- No local filesystem path ingest over HTTP.

## Open Questions Blocking Broad Exposure

- What exact mechanism will select `local_debug` for local API clients without
  creating a misleading production auth model?
- Which future platform surfaces are owner-facing conversation views versus
  broad diagnostic/admin views? Owner-facing routes may eventually expose some
  raw user messages, but broad diagnostics should not.
- Should provider/model labels be exposed as public aliases, hashed labels, or
  omitted entirely in future platform default responses?
- Should source chunk previews ever be available in platform defaults, or only
  behind source-work ownership/source-license policy?
- Should default unexpected-error messages become fully generic before any
  hosted API work begins? This document recommends yes.
