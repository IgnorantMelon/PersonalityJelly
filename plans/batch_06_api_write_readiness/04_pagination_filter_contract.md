# Pagination And Filter Contract

Batch 06 Task 04 defines the shared contract for API list, pagination, ordering, filters, and list
response envelopes. This is a planning artifact only. It does not change current Batch 05 API
behavior, does not add routes, and does not implement repository, cursor, or response-schema changes.

## Current State

Batch 05 exposes a GET-only FastAPI adapter over `personality_jelly.application` inspection
services. Current list responses use `InspectionListResult` from
`src/personality_jelly/application/inspection.py`; there is no `src/personality_jelly/api/schemas.py`
file in the current tree. The existing list envelope contains:

- `items`: returned inspection summaries or details.
- `total_count`: currently the number of returned items, not a guaranteed full matching-row count.
- `limit`: the requested limit when the route accepts one, otherwise `null`.
- `expansion`: summary/detail expansion metadata.

Current list endpoints do not expose `offset`, `cursor`, `has_more`, `next_cursor`, `count`,
`order`, or echoed `filters`. Existing contract tests lock the route set, tags, and query parameter
names.

## Current Batch 05 List Endpoint Inventory

| Endpoint | Current query parameters | Current ordering | Current envelope notes |
| --- | --- | --- | --- |
| `GET /conversations` | `limit` optional, integer `>=1` | `updated_at desc` | `limit` is optional; omitted means unbounded today. `total_count` is returned item count. |
| `GET /characters` | `source_work_id` required, non-empty | `created_at asc`, `id asc` | No `limit`. Missing `source_work_id` parent returns `404` through application validation. |
| `GET /claims` | `character_id` required, `status` optional enum, `claim_type` optional enum | Repository has no explicit order today | No `limit`. Invalid enum values return `422 validation_error`. |
| `GET /memories` | `user_id` required, `character_id` required, `scope` optional enum, `status` optional enum | Repository has no explicit order today | No `limit`. Required user and character links are validated by the application service. |
| `GET /failure-cases` | `conversation_id` optional, `category` optional, `limit` optional integer `>=1` | `created_at desc` | When `conversation_id` is provided, category and limit are applied after loading conversation rows. |
| `GET /llm-traces` | `operation`, `schema_name`, `provider_name`, `model_name` optional strings; `with_errors` optional bool default `false`; `limit` optional integer `>=1` | `created_at desc` | `with_errors=true` is applied after loading filtered traces, then sliced by `limit`. |
| `GET /eval-runs` | `character_id`, `test_suite` optional strings; `limit` optional integer `>=1` | `created_at desc` | Optional identity filters are exact-match selectors. Missing IDs currently produce an empty list. |
| `GET /retrieval-eval-runs` | `character_id`, `source_work_id`, `test_suite` optional strings; `limit` optional integer `>=1` | `created_at desc` | Optional identity filters are exact-match selectors. Missing IDs currently produce an empty list. |

Detail endpoints also expose collection-shaping query parameters that should follow the same naming
and validation style even though they are not top-level list endpoints:

- `GET /conversations/{conversation_id}`: `message_limit`, `include_user`,
  `include_character`, `include_persona_version`, `include_memories`.
- `GET /context-packages/{context_package_id}`: `include_persona_version`, `include_claims`,
  `include_evidence`, `include_evidence_chunks`, `include_memories`, `include_retrieved_chunks`,
  `include_retrieved_chunk_text`.
- `GET /eval-runs/{run_id}`: `failed_only`.
- `GET /retrieval-eval-runs/{run_id}`: `failed_only`, `include_chunks`.

## Limit Contract

Future implementation batches should use one shared limit policy for every top-level list endpoint:

- Default `limit`: `50`.
- Maximum `limit`: `200`.
- Minimum `limit`: `1`.
- Omitted `limit` on new or migrated list endpoints means the default limit, not unbounded output.
- `limit=0`, negative values, non-integers, and values above `200` must return the shared
  `422 validation_error` envelope.
- Detail collection controls such as `message_limit` should keep their own documented defaults but
  should also define an explicit maximum before broad client use. Recommended `message_limit` max:
  `200`.

Existing Batch 05 endpoints must not be changed as part of this planning task. A later migration can
move them to this policy in one coordinated API-contract pass.

## Pagination Decision

Use a cursor-ready contract; do not add offset pagination.

The next implementation should keep existing Batch 05 endpoints limit-only for compatibility until
the list envelope and repository gaps below are addressed. New write-era list endpoints, and any
coordinated migration of Batch 05 lists, should use cursor-based keyset pagination from the start.

Rationale:

- Offset pagination is simple, but it is unstable under writes and expensive on growing diagnostic
  tables.
- Cursor pagination matches the expected write-era API, where conversations, traces, failures,
  memories, and eval runs can be appended while clients page through results.
- Current repositories already express natural sort keys for most list families, but they need
  deterministic tie-breakers before cursors are safe.

Cursor query and response names:

- Request query parameter: `cursor`.
- Response fields: `has_more` and `next_cursor`.
- Cursor values must be opaque to clients. A later implementation can use base64url JSON containing
  a cursor version, order name, and the last item order tuple, but clients must treat the value as an
  uninterpreted string.
- Cursor pagination should fetch `limit + 1` rows to compute `has_more`, return at most `limit`
  items, and emit `next_cursor=null` when no further page exists.
- Do not expose `offset`, `page`, or `page_size` in this API unless a future maintainer explicitly
  chooses a separate admin/export surface.

## Stable Ordering Contract

Every list endpoint must have exactly one documented default order. Add an `id` tie-breaker to every
time-based order before implementing cursors.

| List family | Contract order | Current gap |
| --- | --- | --- |
| Conversations | `updated_at desc`, `id desc` | Repository currently orders by `updated_at desc` only. |
| Characters by source work | `created_at asc`, `id asc` | Already matches the contract. |
| Claims by character | `id asc` until a claim `created_at` or source-order field exists | Repository currently has no explicit order. |
| Memories by user and character | `created_at desc`, `id desc` | Repository currently has no explicit order. |
| Failure cases | `created_at desc`, `id desc` | Repository currently lacks the `id` tie-breaker; conversation path slices in application code. |
| LLM traces | `created_at desc`, `id desc` | Repository currently lacks the `id` tie-breaker; `with_errors` filtering is partly in memory. |
| OOC eval runs | `created_at desc`, `id desc` | Repository currently lacks the `id` tie-breaker. |
| Retrieval eval runs | `created_at desc`, `id desc` | Repository currently lacks the `id` tie-breaker. |
| Source chunks, when a list route is added | `chapter_index asc nulls first`, `paragraph_index asc`, `char_start asc nulls first`, `id asc` | Current repository lacks the final `id` tie-breaker and no API list route exists. |
| Messages within conversation detail | `created_at asc`, `id asc`; `message_limit` returns the last N messages in chronological order | Current repository lacks the `id` tie-breaker. |
| Eval run case results | `created_at asc`, `id asc` | Current repositories lack the `id` tie-breaker. |

Do not add arbitrary client-selected `sort` or `order_by` parameters in the next implementation.
Sorting should remain endpoint-defined until there is a concrete UI or export requirement.

## Filter Naming Conventions

Use exact-match, snake_case query parameters that match persisted response fields wherever possible.

- Identifier filters must end in `_id`: `source_work_id`, `character_id`, `conversation_id`,
  `user_id`, `persona_version_id`, `run_id`, `trace_id`, `chunk_id`.
- Required parent filters come before optional filters in route signatures and OpenAPI output.
- String filters are exact matches unless a future endpoint explicitly names a search mode. Do not
  add substring, regex, fuzzy, or semantic matching filters in API handlers.
- Enum filters use domain enum values exactly as serialized in responses:
  - claim `status`: `candidate`, `verified`, `rejected`, `conflicted`;
  - `claim_type`: `identity`, `appearance`, `personality`, `relationship`, `event`, `ability`,
    `speech`, `world_rule`;
  - memory `scope`: `user_memory`, `relationship_memory`, `session_memory`, `reflective_memory`;
  - memory `status`: `candidate`, `accepted`, `rejected`, `archived`.
- Use `status` when the endpoint has only one status field. If a future endpoint can filter multiple
  statuses, prefix the field, for example `memory_status`, `claim_status`, or `run_status`.
- Use `scope` only for memory scope on `/memories`. Broader endpoints should use `memory_scope`.
- Trace filters stay exact string filters: `operation`, `schema_name`, `provider_name`,
  `model_name`.
- Benchmark filters use `test_suite` for both OOC and retrieval eval runs. Do not introduce
  `suite`, `case_suite`, or `benchmark`.
- Boolean result filters should use affirmative names:
  - `with_errors` for LLM trace list rows that have validation errors;
  - `failed_only` for nested eval case collections;
  - `include_chunks` and other `include_*` names for response expansion only.
- `include_*` parameters are expansions, not filters. They may change payload shape and cost, but
  must not change which top-level resource the endpoint returns.

## List Response Envelope Contract

The cursor-ready list envelope for later implementation should be:

```json
{
  "items": [],
  "count": 0,
  "limit": 50,
  "has_more": false,
  "next_cursor": null,
  "cursor": null,
  "order": "created_at_desc_id_desc",
  "filters": {},
  "total_count": null,
  "expansion": {
    "mode": "summary",
    "expanded": [],
    "omitted": []
  }
}
```

Field expectations:

- `items` is the returned page.
- `count` is always `len(items)`.
- `limit` is the effective limit after applying the default and maximum policy.
- `cursor` echoes the request cursor or `null`.
- `has_more` is `true` only when another page exists for the same filters and order.
- `next_cursor` is an opaque string only when `has_more=true`; otherwise it is `null`.
- `order` names the endpoint-defined order, for example `updated_at_desc_id_desc`.
- `filters` echoes normalized filter values that affected resource selection. Omit unknown or
  ignored parameters; do not echo expansion toggles as filters.
- `total_count` is optional and should be `null` unless the service performs an explicit exact count.
  Do not overload it as returned page count in new schemas.
- `expansion` keeps the current `ExpansionState` convention.

For Batch 05 compatibility, existing `InspectionListResult` can remain as a legacy subset until a
coordinated route-contract migration updates tests and clients. Do not silently change the meaning
of the existing `total_count` field without that migration.

## Invalid Filter And Cursor Error Behavior

All invalid query behavior should continue to use the shared API error envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": {
      "errors": []
    },
    "trace_id": null
  }
}
```

Rules:

- Query type, range, enum, and boolean parsing errors return `422 validation_error` with FastAPI
  field locations such as `["query", "limit"]`.
- `limit` above the maximum returns `422 validation_error`.
- Malformed, expired, or order-mismatched `cursor` values return `422 validation_error` with
  location `["query", "cursor"]`.
- A cursor created for one endpoint, order, or filter set must not be accepted for another endpoint
  or filter set.
- Required parent-resource filters should be validated by application services:
  - missing `source_work_id` parent for `/characters` returns `404 not_found`;
  - missing `character_id` parent for `/claims` returns `404 not_found`;
  - missing `user_id` or `character_id` parent for `/memories` returns `404 not_found`.
- Optional filters on diagnostic global lists are selectors, not parent lookups. A syntactically
  valid but unmatched `character_id`, `source_work_id`, `test_suite`, `operation`, `provider_name`,
  or `model_name` should return `200` with an empty `items` list unless a future endpoint is
  explicitly modeled as a child collection.
- Unknown query parameter names are not part of this contract. Batch 05 currently relies on FastAPI
  defaults. If a future implementation adopts strict query models, unknown parameters should return
  `422 validation_error` in the same envelope.

## Repository And Application Prerequisites

Before implementing cursor pagination or migrating existing list endpoints, add these prerequisites
in a focused implementation batch:

- Add shared list constants and parsing helpers, for example `DEFAULT_LIST_LIMIT = 50` and
  `MAX_LIST_LIMIT = 200`, in an application/API boundary module rather than duplicating values in
  route handlers.
- Add API-specific list schemas or a transport-neutral replacement for `InspectionListResult` so
  `count`, `has_more`, `next_cursor`, `cursor`, `order`, and normalized `filters` have one source of
  truth.
- Add deterministic `order_by(..., id)` tie-breakers to every repository list query named above.
- Add repository-level `limit` support for `CharacterRepository.list_by_source_work`,
  `CanonClaimRepository.list_by_character`, `MemoryRepository.list_for_user_character`,
  `FailureCaseRepository.list_by_conversation`, message lists, and eval case-result lists instead of
  slicing unbounded application lists.
- Add `limit + 1` query support for cursor readiness.
- Move `LLMRawOutputRepository.list_recent(with_errors=True)` filtering into SQL or add a persisted
  error-count/error-present column before relying on it for large trace pages.
- Add missing indexes only when the cursor implementation touches that list family. Likely indexes:
  `(updated_at, id)` for conversations, `(created_at, id)` for memory/failure/trace/eval tables, and
  `(character_id, id)` for claims until a better claim order field exists.
- Decide whether claim rows need a `created_at` or source-order field. Until then, `id asc` is the
  only deterministic claim order contract.

## Compatibility Guidance For Batch 05

Current Batch 05 behavior remains compatible and intentionally unchanged:

- Keep the existing GET-only route set.
- Keep existing query parameter names and defaults.
- Keep optional `limit` semantics on current endpoints: omitted still means unbounded where Batch 05
  currently behaves that way.
- Keep existing list envelope fields and do not add cursor fields in this planning branch.
- Keep existing validation behavior: invalid limits and enum values return `422 validation_error`;
  missing detail resources return `404 not_found`; optional unmatched diagnostic filters return
  empty lists.
- Do not add tests in this planning task. Later implementation batches must update
  `tests/test_api_contract.py` and route tests when they intentionally migrate list behavior.

The recommended migration path is:

1. Add deterministic ordering and shared limit constants.
2. Add a cursor-ready list envelope without changing route behavior.
3. Migrate one route family at a time behind updated contract tests.
4. Add cursor parameters only after the repository query for that family has stable ordering and
   `limit + 1` support.

## Open Questions

- Should exact `total_count` ever be computed for diagnostic tables, or should cursor lists always
  leave it `null` for performance?
- Should claim ordering stay `id asc`, or should a later schema add `created_at` or extracted
  source-order metadata?
- Should strict unknown-query-parameter rejection be adopted globally, or should the API preserve
  FastAPI's current permissive behavior for compatibility?
