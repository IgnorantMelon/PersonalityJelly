# Batch 11 Provider-Backed Persona Setup API

Batch 11 is the implementation batch after Batch 10 source/character API closeout. Its purpose is
to expose the first true provider-backed write workflow:

- `POST /characters/{character_id}/persona-setup-runs`

This batch starts from the accepted Batch 10 state where `POST /source-works` and deterministic
`POST /characters` already create the prerequisite records. Do not mix source ingest or character
creation work into Batch 11.

Follow `VIBE_CODING_GUIDE.md`, the Batch 08 workflow persistence closeout, the accepted Batch 09
contracts, and the Batch 10 handoff:

- `plans/batch_09_provider_backed_api_planning/02_character_persona_setup_api_contract.md`
- `plans/batch_09_provider_backed_api_planning/03_provider_backed_write_contract_matrix.md`
- `plans/batch_10_provider_backed_source_character_api/BATCH_10_PROVIDER_BACKED_SOURCE_CHARACTER_API.md`
- `plans/batch_08_api_workflow_persistence/BATCH_08_CLOSEOUT.md`

Batch 11 development task prompts are development tasks only. Coordinator integration, route audit,
final regression runs, docs/status updates, and post-batch handoff notes are batch acceptance work,
not numbered implementation prompts.

## Scope Decision

Implement exactly one new provider-backed route:

- `POST /characters/{character_id}/persona-setup-runs`

The route runs Reader extraction, Verifier validation, and persona compilation for an existing
character. It is synchronous in this batch, but the `*-runs` route shape preserves a future async
boundary.

Keep these deferred:

- combined `POST /character-persona-setup-runs`
- source ingest, character create, turn execution, summary generation, benchmark execution routes
- resume/repair/cleanup routes for partial setup attempts
- async queues, uploads, URL fetches, embeddings/source enrichment, auth/workspace/platform, UI,
  deployment, CORS, cursor migrations, external observability, graph/vector systems, or prompt
  controls over HTTP

## Planning Branch

This Batch 11 plan is created on:

| Branch | Branch base | Purpose |
| --- | --- | --- |
| `planning/batch-11-provider-persona-setup` | `dev` at Batch 10 closeout commit `c5fbbee` | Batch 11 plan and task prompts only. |

## Implementation Branches

Implementation should start from clean updated `dev` after this plan is accepted. Workers must use
isolated `git worktree` checkouts under `C:\Projects\PersonalityJelly-worktrees` or another
coordinator-approved writable root. Keep the root checkout on `dev` for coordination/integration;
do not have workers implement by switching branches in the root checkout.

Preserve the dependency order below. Task 02 starts from the completed and pushed Task 01 branch.
Task 03 starts from the completed and pushed Task 02 branch.

| Task | Branch | Branch base | Depends on | Main output |
| --- | --- | --- | --- | --- |
| 01 Provider Trace Foundation | `feature/api-persona-setup-provider-trace-foundation` | clean `dev` after plan acceptance | Batch 08 trace/workflow foundations | Setup-specific provider/model bundles and Reader/Verifier/persona compiler trace-correlation plumbing. |
| 02 Persona Setup Application Workflow | `feature/api-persona-setup-application-workflow` | completed Task 01 branch | 01 | `run_character_persona_setup_workflow`, staged commits, workflow/audit/link/idempotency success/failed/partial outcomes. |
| 03 Persona Setup API Route | `feature/api-persona-setup-route` | completed Task 02 branch | 01, 02 | Thin `POST /characters/{character_id}/persona-setup-runs` adapter, schemas, redaction, replay/conflict, OpenAPI and route tests. |

Suggested worker worktrees:

| Task | Worktree |
| --- | --- |
| 01 | `C:\Projects\PersonalityJelly-worktrees\batch11-01-persona-setup-provider-trace` |
| 02 | `C:\Projects\PersonalityJelly-worktrees\batch11-02-persona-setup-application` |
| 03 | `C:\Projects\PersonalityJelly-worktrees\batch11-03-persona-setup-route` |

Recommended integration branch:

- `integration/batch-11-persona-setup-api`

The coordinator should create the integration branch from clean `dev`, merge accepted Tasks 01, 02,
and 03 in order, then run the batch acceptance checks below before final `dev` integration.

## Accepted Route Contract

Route:

- `POST /characters/{character_id}/persona-setup-runs`

Workflow:

- workflow type: `character_persona.setup`
- audit operation: `character_persona.setup`
- provider-backed: yes
- terminal statuses: `completed`, `failed`, `partial`
- success status: `201 Created`
- required idempotency: `Idempotency-Key` header, with optional body `idempotency_key` mirror

Request body:

- `source_work_id` required; must match the stored character's `source_work_id`
- `provider` required; first implementation supports `stub` and `env`
- `workflow_options` optional; first implementation supports `max_chunks` only
- `actor` required
- `request_id` optional; must match `X-Request-ID` when both are supplied
- `idempotency_key` optional body mirror; must match the header when supplied
- `metadata` optional sanitized labels only

Provider body:

```json
{
  "provider": {
    "source": "stub",
    "roles": {
      "reader": {"model": "stub"},
      "verifier": {"model": "stub"},
      "persona_compiler": {"model": "stub"}
    }
  }
}
```

Accepted provider rules:

- `stub` uses the existing local testing provider pattern.
- `env` resolves providers from existing `PJ_*` settings.
- role model values are model labels only, not provider config.
- missing role model values inherit the resolved bundle-level model.
- request bodies must not accept API keys, bearer tokens, base URLs, headers, provider request
  payloads, prompts, server-local config paths, or raw provider config.

Workflow step names:

- `setup_preflight`
- `reader_extract`
- `verifier_validate`
- `persona_compile`
- `terminal_audit`
- `idempotency_record`

## Staged Persistence Contract

Use the accepted staged boundary from Batch 09:

| Stage | Commit boundary | Failure state |
| --- | --- | --- |
| Request shape and idempotency conflict | No new persistence. | `422 validation_error` or `409 conflict`. |
| Workflow start and preflight | Persist running workflow and input links. | Missing character/source or source mismatch marks workflow `failed`; no business partial. |
| Reader provider call and validation | Persist Reader trace when raw output exists. | Provider/validation failure before domain rows is `provider_failure` or `provider_validation_error`; workflow `failed`. |
| Reader claims/evidence persistence | Commit candidate claims, evidence refs, trace links, workflow links. | Later failures are `partial`. |
| Verifier provider call and validation | Persist Verifier trace. | If Reader rows exist, failures are `partial_persistence`. |
| Verifier claim/conflict persistence | Commit claim status updates and conflicts. | No verified claims or compiler failures are `partial`. |
| Persona compiler provider call and validation | Persist compiler trace. | After verified claims exist, failures are `partial`. |
| Persona version, terminal audit, workflow completion, idempotency record | Commit terminal success and replay together. | Terminal commit failure must roll back persona version; earlier staged rows remain partial. |

Do not delete, merge, or overwrite partially persisted canon rows automatically. Resume, cleanup,
deduplication, and review policies are deferred to later work.

## Storage And Migration Expectations

No schema migration is expected for Batch 11. Use existing tables:

- `workflow_runs`
- `workflow_run_links`
- `audit_events`
- `idempotency_records`
- `llm_raw_outputs`
- `canon_claims`
- `evidence_refs`
- `claim_conflicts`
- `persona_versions`

Use workflow links and `result.persisted_ids` for route-specific many-ID lists. Do not expand
`WorkflowRelatedIds` unless a focused implementation proves it is simpler and remains tested.

If a task unexpectedly needs a schema migration, stop and update the plan before implementing it.

## Batch Acceptance Requirements

The coordinator must verify these after the development task branches are integrated:

- route audit confirms Batch 11 added only `POST /characters/{character_id}/persona-setup-runs`
- route handler is a thin adapter over `personality_jelly.application`
- no API handler calls extraction, persona, provider, repository, or semantic modules directly
- setup requires idempotency and replays success, failure, and partial terminal payloads without
  provider calls or duplicate domain rows
- workflow links exist for source work, character, traces, claims, evidence refs, conflicts,
  persona version, audit event, and idempotency record where applicable
- Reader, Verifier, and compiler LLM traces carry request/workflow/step correlation
- failed and partial workflows expose sanitized diagnostics through existing inspection routes
- default write responses and error envelopes never include raw source text, chunk text, evidence
  excerpts, prompts, provider payloads, provider config, raw outputs, stack traces, SQL, local
  paths, secrets, or auth headers
- OpenAPI contract exposes only the accepted setup route and safe schemas
- focused task tests pass
- full pytest passes
- `README.md`, `VIBE_CODING_GUIDE.md`, and any post-batch status artifact accurately describe
  implemented and deferred scope

## Deferred Handoff After Batch 11

After Batch 11, the next major milestone should be single-character MVP capability validation
across source ingest, character creation, persona setup, conversation turns, memory boundaries,
diagnostics, and benchmarks. Do not start multi-work, multi-character, workspace, UI, or platform
expansion until that validation checkpoint is explicit.
