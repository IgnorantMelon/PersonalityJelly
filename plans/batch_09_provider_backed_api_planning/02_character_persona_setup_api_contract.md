# Task 02: Character Persona Setup API Contract

Batch 09 planning artifact for a future provider-backed character/persona setup API. This document
does not implement routes, schemas, migrations, tests, or provider behavior.

## Recommendation

Implement character creation and provider-backed persona setup as separate routes:

- `POST /characters`
- `POST /characters/{character_id}/persona-setup-runs`

`POST /characters` is deterministic and should use the existing write envelope, persistent audit,
workflow, and optional idempotency behavior already proven by conversation creation and manual
memory writes.

`POST /characters/{character_id}/persona-setup-runs` should be the first provider-backed candidate
only after its application service owns staged commits, trace collection, partial-persistence
normalization, and mandatory idempotency. It should run synchronously in the first implementation
batch, but its route name should model the operation as a workflow run so a later async queue can
reuse the same result shape.

Do not implement a combined "create character and run setup" route first. Keep it as a deferred
convenience route because combining deterministic character creation with provider-backed setup
makes retry and partial-persistence semantics harder to explain.

## Existing Service Mapping

Current reusable pieces:

- Character creation: `personality_jelly.characters.create_character`.
- Setup orchestrator: `personality_jelly.application.build_character_persona`.
- Reader extraction: `personality_jelly.extraction.run_reader_extraction` and
  `extract_candidate_claims`.
- Verifier validation: `personality_jelly.extraction.verify_candidate_claims`.
- Persona compilation: `personality_jelly.persona.compile_persona_version`.
- Provider resolution patterns: `personality_jelly.application.providers`.
- Durable workflow foundation: `CorrelationContext`, `WorkflowContext`,
  `WorkflowRun`, `WorkflowRunLink`, and `WorkflowResponseSummary`.
- Durable idempotency foundation: `IdempotencyRecord`, request hashing, replay, and conflict
  detection.
- Persistent audit foundation: `AuditEvent`, `LocalActorContext`, failure audit construction,
  and metadata sanitization.
- API response redaction foundation: `personality_jelly.api.redaction.redact_payload`.

The future route must not call the lower extraction/persona functions directly from
`personality_jelly.api`. Add or harden an application service that wraps the workflow and returns a
strict transport-neutral result.

## Route Candidates

### Recommended Deterministic Route: `POST /characters`

Creates one character for an existing source work. This route is not provider-backed.

Workflow type:

- `character.create`

Audit operation:

- `character.create`

Request body:

| Field | Required | Notes |
| --- | --- | --- |
| `source_work_id` | yes | Existing source work. |
| `canonical_name` | yes | Normalized like `create_character`; blank after trimming is `422`. |
| `aliases` | no | Normalized, deduplicated, canonical name removed. |
| `character_id` | no | Optional explicit ID; collision with different data is `409`. |
| `actor` | yes | Local attribution context, not auth. |
| `request_id` | no | Body value must match `X-Request-ID` when both are supplied. |
| `idempotency_key` | no | Body value must match `Idempotency-Key` when both are supplied. |
| `metadata` | no | Bounded client labels only; no prompts, secrets, provider config, or local paths. |

Success response:

- HTTP `201 Created` for a new character.
- Replayed response uses the stored status code.
- Top-level envelope fields: `request_id`, `workflow_id`, `workflow_type`, `status`, `ids`,
  `warnings`, and `result`.
- `ids`: `source_work_id`, `character_id`, `audit_event_ids`.
- `result.character`: `character_id`, `source_work_id`, `canonical_name`, `aliases`,
  `latest_persona_version_id=null`.
- `result.audit_event`: redacted persistent audit event summary.

Errors:

- `404 not_found`: missing source work.
- `409 conflict`: duplicate explicit `character_id`, duplicate name in the same source work, or
  idempotency request hash mismatch.
- `422 validation_error`: blank canonical name, malformed request correlation, invalid actor, or
  path/body mismatch if a future path variant is added.
- `500 unexpected_error`: sanitized storage defects.

Transaction boundary:

- One transaction for source-work lookup, character insert, audit event, workflow run/link
  completion, and idempotency replay storage.
- Persist nothing on validation, lookup, or conflict before the transaction commits.
- If audit persistence fails, roll back the character insert.

### Recommended Provider-Backed Route: `POST /characters/{character_id}/persona-setup-runs`

Runs Reader extraction, Verifier validation, and persona compilation for an existing character.

Workflow type:

- `character_persona.setup`

Workflow step names:

- `setup_preflight`
- `reader_extract`
- `verifier_validate`
- `persona_compile`
- `terminal_audit`
- `idempotency_record`

Audit operation:

- `character_persona.setup`

The first implementation may use this string even if `AuditOperation` is not expanded yet, because
current audit payloads accept string operations. Adding enum values is an implementation-batch
choice.

Request body:

| Field | Required | Notes |
| --- | --- | --- |
| `source_work_id` | yes | Must match the character's `source_work_id`; mismatch is `422`. |
| `provider` | yes | Provider role bundle/config source, described below. |
| `workflow_options` | no | Extraction/verification/compilation controls, described below. |
| `actor` | yes | Local attribution context; provider-backed setup must be attributable. |
| `request_id` | no | Body/header match rule from current write routes. |
| `idempotency_key` | yes | Required for provider-backed setup; body/header match rule applies. |
| `metadata` | no | Sanitized labels only. |

Path/body rules:

- Path `character_id` is authoritative.
- The body must not contain a different `character_id`.
- `source_work_id` is required even though it can be derived from the character. Keeping it explicit
  prevents hidden single-work assumptions and makes idempotency hashing stable.

Provider role bundle:

```json
{
  "provider": {
    "source": "stub | env | named_config",
    "roles": {
      "reader": {"model": "model-or-alias"},
      "verifier": {"model": "model-or-alias"},
      "persona_compiler": {"model": "model-or-alias"}
    }
  }
}
```

Implementation notes:

- The first implementation can support only `stub` and `env` if that matches current provider
  resolution.
- Do not accept raw API keys, bearer tokens, base URLs, headers, provider request payloads, or
  server-local config paths in the HTTP body.
- Add a setup-specific application provider bundle, for example reader/verifier/persona compiler
  providers and model configs. Do not reuse the turn `roleplay` naming in the API contract.
- Missing role overrides may inherit from the bundle-level provider/model if the application
  service documents that default.

Workflow options:

| Field | Default | Notes |
| --- | --- | --- |
| `max_chunks` | `null` | Same meaning as current setup service; `null` means all chunks. |
| `rerun_policy` | `new_attempt` | First implementation should create a new setup attempt for a new idempotency key. |
| `require_verified_claims` | `true` | If no verified claims exist after Verifier, do not compile persona. |
| `compile_persona` | `true` | Keep `false` deferred unless the implementation intentionally supports extraction-only setup. |
| `response_detail` | `summary` | Default response returns IDs/counts only; `debug` is deferred to explicit local-debug policy. |

Do not add semantic options that change Reader, Verifier, or compiler prompts in this API batch.

Success response:

- HTTP `201 Created` when a new setup run completes and creates a persona version.
- Replayed response uses the stored status code and must not call providers.

Response fields:

| Field | Notes |
| --- | --- |
| `request_id` | Always returned. |
| `workflow_id` | Always returned once application service starts. |
| `workflow_type` | `character_persona.setup`. |
| `status` | `completed`. |
| `ids.source_work_id` | Source work used by the setup. |
| `ids.character_id` | Character path ID. |
| `ids.persona_version_id` | Created persona version. |
| `ids.llm_trace_ids` | All setup trace IDs collected by Reader, Verifier, and compiler. |
| `ids.audit_event_ids` | Terminal audit event IDs. |
| `result.character` | Compact character identity and latest persona version ID. |
| `result.claims` | Candidate, verified, rejected/conflicted, and conflict ID lists plus counts. |
| `result.evidence_refs` | Evidence ref IDs, source chunk IDs, and counts; no excerpts by default. |
| `result.persona_version` | Persona version ID, version number, source claim IDs, created-at metadata; no raw persona rules by default. |
| `result.workflow` | Step status summary and persisted ID summary. |
| `warnings` | Non-fatal warnings only. Provider step failures are not warnings. |

Default response must not include raw source text, evidence excerpts, claim reasoning, raw persona
rules, prompts, provider request/response payloads, trace payloads, secrets, local paths, or stack
traces.

Deferred combined route:

- Candidate name: `POST /character-persona-setup-runs`.
- It would accept `source_work_id`, `character: {character_id, canonical_name, aliases}`, provider,
  workflow options, actor, request correlation, and mandatory idempotency.
- It should not be implemented until the separate routes prove replay and partial-persistence
  behavior.

## Transaction And Partial-Persistence Model

Provider-backed setup must be staged. The application service, not the route handler, owns these
boundaries. A future `get_write_session` dependency can still commit at request end, but the setup
service must be allowed to commit completed stages so failure diagnostics survive provider errors.

Recommended rule:

- Diagnostic-only records are `workflow_runs`, `workflow_run_links`, `audit_events`,
  `idempotency_records`, and `llm_raw_outputs`.
- Business/domain records are `characters`, `canon_claims`, `evidence_refs`, `claim_conflicts`,
  and `persona_versions`.
- Return workflow status `failed` when only diagnostic records exist.
- Return workflow status `partial` when any setup business/domain record was committed before a
  later step failed.

Stage boundaries:

| Stage | Commit Boundary | Failure State |
| --- | --- | --- |
| Request shape and idempotency conflict | No new persistence. | `422` or `409`; no workflow ID unless a matching replay exists. |
| Workflow start and preflight | Persist `workflow_runs(status=running)` and input links after request/idempotency validation. | Missing source/character or source mismatch marks workflow `failed`; no business partial. |
| Reader provider call and validation | Persist Reader `LLMRawOutput` with request/workflow/step when raw output exists. | Provider exception before domain rows is `provider_failure` or `provider_validation_error`; workflow `failed`, no business partial. |
| Reader claims/evidence persistence | Commit candidate `canon_claims`, `evidence_refs`, trace links, and workflow links together. | Later failures are `partial`; response includes candidate/evidence IDs. |
| Verifier provider call and validation | Persist Verifier trace with step `verifier_validate`. | If Reader domain rows are committed, provider/validation failure is `partial_persistence` with cause details. |
| Verifier claim/conflict persistence | Commit status updates and `claim_conflicts` together. | Later no-verified-claims or compiler failures are `partial`. |
| Persona compiler provider call and validation | Persist compiler trace with step `persona_compile`. | After verified claims exist, provider/validation failure is `partial`. |
| Persona version, terminal audit, workflow completion, idempotency record | Commit persona version, terminal audit event, completed workflow status, links, and idempotency replay together. | If terminal commit fails, persona version must roll back; prior claims/evidence/verification remain partial. |

Partial states to expose:

| State | Persisted IDs | Failed Step | Retry Hint |
| --- | --- | --- | --- |
| `workflow_failed_no_domain` | `workflow_id`, optional `llm_trace_ids`, `audit_event_ids` | `setup_preflight` or `reader_extract` | Fix request/provider config and retry with a new idempotency key. |
| `reader_persisted_verifier_failed` | candidate claim IDs, evidence ref IDs, Reader trace IDs | `verifier_validate` | Inspect workflow/trace IDs, then retry with a new key or future resume route. |
| `verification_persisted_no_verified_claims` | candidate/updated claim IDs, evidence ref IDs, conflict IDs | `persona_compile` precondition | Review source/name/aliases or add manual claim review; do not auto-compile. |
| `verification_persisted_compiler_failed` | candidate/verified claim IDs, evidence ref IDs, conflict IDs, compiler trace ID if available | `persona_compile` | Retry with a new key after provider issue is resolved; future resume may reuse verified claims. |
| `terminal_commit_failed` | candidate/verified claim IDs, evidence ref IDs, conflict IDs; no persona ID if rolled back | `terminal_audit` or `idempotency_record` | Treat as operator investigation; replay may not exist. |

Do not delete or overwrite partially persisted canon rows automatically. Later cleanup, review, and
resume policies are deferred.

## Provider Failure Behavior

Use the existing normalized error families and extend API status mapping only where needed.

| Condition | HTTP | Error Code | Notes |
| --- | --- | --- | --- |
| Provider unavailable, timeout, or transport error before business rows | `502` or `503` | `provider_failure` | Include request/workflow IDs and safe failed step. |
| Provider returned malformed JSON or Pydantic-invalid shape before business rows | `502` | `provider_validation_error` | Include safe trace IDs if persisted. |
| Provider returned valid schema with invalid semantic references, such as unknown chunk or claim ID | `502` | `provider_validation_error` | Treat as provider validation failure, not request validation. |
| Provider failure after claims/evidence or verification rows committed | `500` | `partial_persistence` | Include `cause=provider_failure` or `cause=provider_validation_error`. |
| No candidate claims from Reader | `422` or `502` by implementation decision | `no_candidate_claims` under workflow `failed` | Prefer `422` if provider output is valid but unusable for the requested character. |
| No verified claims after Verifier | `500` | `partial_persistence` | Business rows exist; include retry/review hint. |

Error details must include:

- `request_id`;
- `workflow_id` when started;
- `workflow_type`;
- `failed_step`;
- `persisted_ids`;
- `llm_trace_ids`;
- `audit_event_ids`;
- `retry_hint`;
- sanitized `details` with no raw provider payloads.

`trace_id` in the current error envelope may reference one representative `llm_trace_id` for
compatibility, but `llm_trace_ids` must be a list in details.

## Workflow Runs And Links

Workflow run fields:

- `request_id`;
- `workflow_id`;
- `workflow_type=character_persona.setup`;
- `status=running|completed|failed|partial`;
- `persisted_ids` compact JSON;
- `warnings`;
- `error_code`, `error_details`, `failed_step` on failed/partial outcomes.

Workflow link relations:

| Entity Type | Relation | When |
| --- | --- | --- |
| `source_work` | `input` | Preflight succeeds. |
| `character` | `input` | Preflight succeeds. |
| `llm_trace` | `trace` | Reader, Verifier, and compiler traces are persisted. |
| `canon_claim` | `created` | Reader candidate claims are persisted. |
| `canon_claim` | `updated` | Verifier updates claim status/confidence/reasoning. |
| `evidence_ref` | `created` | Reader evidence refs are persisted. |
| `claim_conflict` | `created` | Verifier conflicts are persisted. |
| `persona_version` | `result` | Persona compile succeeds. |
| `audit_event` | `audit` | Terminal success/failure/partial audit is persisted. |
| `idempotency_record` | `idempotency` | Terminal replay record is stored. |

If `WorkflowRelatedIds` remains narrow, use `workflow_run_links` as the authoritative place for
claim/evidence/conflict ID lists and put those IDs under the response `result.persisted_ids`.
Expanding `WorkflowRelatedIds` with `canon_claim_ids`, `evidence_ref_ids`, and `claim_conflict_ids`
is useful but not required if links are complete.

## Audit Contract

Required operations:

- `character.create`: deterministic character creation.
- `character_persona.setup`: terminal event for setup success, failure, or partial.

Optional step audit operations are deferred:

- `character_persona.reader_extract`
- `character_persona.verifier_validate`
- `character_persona.persona_compile`

First implementation should prefer one terminal audit event to avoid noisy audit lists. Step-level
debugging should come from workflow links and LLM trace IDs.

Audit related IDs:

- `source_work_id`;
- `character_id`;
- `persona_version_id` when created;
- representative `llm_trace_id` if current audit shape accepts only one;
- additional trace IDs and claim/evidence/conflict IDs in sanitized metadata or workflow links.

Audit result:

- `succeeded` when persona version is committed.
- `failed` when no business/domain setup rows were committed.
- `partial` when claims/evidence/verification rows were committed but setup did not complete.

Audit metadata must include sanitized request/workflow IDs, failed step on failure, counts, and
retry hint. It must not include source text, prompt text, provider payloads, secrets, local paths,
or stack traces.

## Idempotency Policy

Provider-backed persona setup must require `Idempotency-Key` or body `idempotency_key`.

Scope:

- `workflow_type=character_persona.setup`
- `idempotency_key`
- canonical request hash over body and path-derived `character_id`, excluding `request_id` and
  `idempotency_key`.

Replay:

- Same key and same request hash returns the stored completed, failed, or partial response.
- Replay must not call providers, create new traces, create new claims, update claims, or create a
  new persona version.
- Replayed response uses the originally stored status code.

Conflict:

- Same key with a different request hash returns `409 conflict`.
- Details include `workflow_type`, sanitized conflict reason, and the existing idempotency record
  correlation if safe.

Partial replay:

- Same key after a partial outcome returns the same partial payload/error envelope.
- It does not attempt to resume or repair the workflow.
- A future resume route may use the stored workflow ID, but that is deferred.

New attempt:

- A new idempotency key starts a new setup attempt.
- The first implementation should not try to deduplicate setup by character/source alone.
- Reusing existing candidate claims or verified claims across attempts is deferred.

In-progress or crashed attempts:

- If an idempotency record or workflow run exists with `running` and no terminal replay payload,
  return `409 conflict` with `retry_hint=inspect_workflow_run`.
- Do not run providers twice under the same key.

## Redaction Guarantees

Default write responses and error envelopes must use the safe API redaction profile. They may expose
IDs, counts, statuses, timestamps, enum labels, and sanitized warning/error codes.

Never expose:

- API keys, bearer tokens, cookies, auth headers, or environment secret values.
- Raw provider config, raw provider request payloads, raw provider response payloads, base URLs, or
  headers.
- Full prompts, prompt-like chat messages, JSON-schema compatibility instructions, or assembled
  prompt sections.
- Raw source text, source chunk text, evidence excerpts, source previews, or chunk previews by
  default.
- Memory-like content found in actor metadata, workflow metadata, warnings, provider outputs, or
  error details.
- Local filesystem paths, database URLs, stack traces, SQL statements, or raw exception bodies.
- LLM trace `raw_output`, `parsed_output`, `response_schema`, or `validation_errors` in the setup
  response.

Default setup response should use:

- claim/evidence/persona IDs and counts instead of raw claim content and evidence excerpts;
- persona version ID and source claim IDs instead of raw persona rules;
- provider role aliases and model aliases only when the profile allows them;
- `llm_trace_ids` for local debugging through trace inspection routes.

Local debug exposure remains a separate policy decision. Include flags or `response_detail` must
not bypass redaction by themselves.

## Application-Service Prerequisites

Before route implementation, add or harden:

1. `create_character_workflow(session, request)` for deterministic character creation.
2. `run_character_persona_setup_workflow(session, request)` as the API-ready staged setup wrapper.
3. Setup-specific provider/model role bundle models for Reader, Verifier, and persona compiler.
4. Context-aware trace recorder plumbing so Reader, Verifier, and compiler traces carry
   `request_id`, `workflow_id`, `workflow_step`, and related IDs.
5. Step result collection so the workflow result can return all trace IDs and persisted domain IDs.
6. Failure normalization around provider transport errors, Pydantic validation errors, provider
   semantic-reference errors, no-candidate/no-verified preconditions, and terminal commit failures.
7. Staged transaction helpers or an explicit unit-of-work policy that allows commit per completed
   setup stage.
8. Redacted response models for setup success and partial/error payloads.
9. Idempotency replay storage for completed, failed, and partial terminal outcomes.

## Focused Implementation Tests

Application tests:

- `create_character_workflow` persists character, workflow run/link, audit event, and optional
  idempotency replay in one transaction.
- Duplicate character name and explicit ID collision return conflict and do not persist audit or
  workflow completion rows.
- Setup success with deterministic fake providers returns character ID, candidate claim IDs,
  evidence ref IDs, verified claim IDs, conflict IDs, persona version ID, audit IDs, workflow ID,
  and Reader/Verifier/compiler trace IDs.
- Reader provider transport failure before claims marks workflow failed, stores sanitized failure
  audit/idempotency data, and creates no canon/persona rows.
- Reader provider validation failure with a persisted trace returns safe trace ID and no raw output.
- Verifier provider validation failure after Reader persistence marks workflow partial and returns
  candidate/evidence IDs without creating a persona.
- Verifier output with no verified claims marks workflow partial and returns a no-verified-claims
  retry hint.
- Persona compiler validation failure after verification marks workflow partial and returns compiler
  trace ID when available.
- Terminal audit/idempotency failure does not commit persona version while prior staged rows remain
  visible as partial.
- Same idempotency key and request hash replays without provider calls or duplicate rows.
- Same idempotency key with different request hash returns conflict.
- Partial replay returns the stored partial payload without resuming.

API tests:

- `POST /characters` success, generated request ID, header/body request ID mismatch, optional
  idempotency replay, duplicate name conflict, missing source work, and redacted audit payload.
- `POST /characters/{character_id}/persona-setup-runs` requires idempotency key.
- Setup path/body source mismatch returns `422` before provider calls.
- Setup success returns `201` with no raw source text, prompt text, provider payloads, evidence
  excerpts, raw persona rules, or trace payloads.
- Provider failure, provider validation failure, and partial-persistence error envelopes include
  request/workflow IDs, failed step, persisted IDs, retry hint, and safe trace IDs.
- OpenAPI schema for default setup response does not contain raw prompt, raw output, parsed output,
  source text, evidence excerpt, stack trace, API key, or provider config fields.

Storage/correlation tests:

- Workflow links exist for source work, character, claims, evidence refs, conflicts, persona
  version, traces, audit event, and idempotency record.
- LLM trace rows from Reader, Verifier, and compiler store request/workflow/step correlation.
- Audit metadata sanitizer redacts secrets, provider config, provider payloads, paths, prompts,
  trace payloads, source text, and stack traces recursively.
- Idempotency records store redacted terminal replay payloads for success and partial outcomes.

## Explicit Non-Goals

- No route, schema, migration, source, test, prompt, provider, retrieval, benchmark, or persona
  behavior changes in Batch 09 Task 02.
- No source ingest route in this task.
- No turn execution, summary generation, OOC benchmark execution, retrieval benchmark execution,
  or cursor pagination migration.
- No auth, workspace, platform roles, CORS, deployment, UI, queue, external observability, billing,
  quotas, or rate limits.
- No raw provider config or server-local file path input over HTTP.
- No semantic behavior changes, keyword rules, regex rules, fixed-vocabulary judgments, prompt
  edits, model-routing framework, graph/vector database, or third-party memory system.
- No automatic deletion, merge, or overwrite of partially persisted canon rows.
- No manual canon review/edit API in this route batch.

## Deferred Decisions

- Whether to add the combined `POST /character-persona-setup-runs` convenience route after the
  separate routes are accepted.
- Whether setup should become async with `202 Accepted`, polling, cancellation, and queue-backed
  execution.
- Whether to add a resume route that can continue from persisted Reader or Verifier outputs instead
  of starting a new attempt.
- Whether to reuse existing candidate/verified claims for later setup attempts or always create a
  new extraction attempt.
- Whether to expose local-debug claim content, evidence excerpts, and persona rules through this
  write response or only through existing/future read-only inspection routes.
- Whether to expand `WorkflowRelatedIds` with claim/evidence/conflict lists or rely on workflow
  links plus response `result.persisted_ids`.
- Whether terminal audit should remain one event or add per-step audit events after volume and
  inspection usability are evaluated.
- Whether no-candidate Reader output should be an HTTP `422` business validation failure or a
  `502 provider_validation_error` for strict clients.
- Retention and cleanup policy for abandoned partial setup attempts.
