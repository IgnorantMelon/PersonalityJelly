# Batch 09 Provider-Backed API Planning

Batch 09 is the planning batch after Batch 08 API Workflow Persistence Foundation. Its purpose is
to select and specify the first provider-backed HTTP workflow surface before implementation begins.

Follow `VIBE_CODING_GUIDE.md`, especially the multi-agent orchestration mode and the Batch 08
closeout. Batch 09 should produce implementation-ready contracts and task prompts. It must not add
provider-backed write routes during the planning batch.

## Batch Goals

- Evaluate source ingest and character/persona setup as the first provider-backed API candidates.
- Define route contracts, request/response models, status codes, and error envelopes.
- Map every candidate workflow to Batch 08 audit, workflow-run/link, idempotency, redaction, and
  provider failure/partial-persistence contracts.
- Identify transaction boundaries, persisted IDs, replay behavior, conflict behavior, and partial
  persistence states before implementation.
- Produce the next implementation batch plan only after the contracts are explicit.

## Non-Goals

- Do not implement source ingest, character/persona setup, turn execution, summary generation,
  benchmark execution, or any other provider-backed HTTP write route in Batch 09.
- Do not change prompts, semantic behavior, provider selection, retrieval behavior, memory guard
  rules, benchmark pass/fail logic, or LLM provider internals.
- Do not add auth, workspace/platform features, CORS, deployment, UI, queues, external
  observability, graph/vector databases, or third-party memory systems.
- Do not migrate existing read-only list routes to cursor pagination.

## Starting Point

Batch 08 closeout verified:

- append-only audit event persistence;
- workflow run/link persistence and LLM trace correlation fields;
- durable idempotency replay/conflict behavior;
- provider failure and partial-persistence contracts;
- read-only audit/workflow inspection routes.

Relevant inputs:

- `VIBE_CODING_GUIDE.md`
- `plans/batch_08_api_workflow_persistence/BATCH_08_CLOSEOUT.md`
- `plans/batch_06_api_write_readiness/01_write_workflow_boundary_design.md`
- `plans/batch_06_api_write_readiness/03_api_redaction_policy.md`
- `plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`
- existing source ingestion, character setup, extraction, verifier, and persona application services.

## Shared Planning Rules

- Use the dependency-branch workflow in `VIBE_CODING_GUIDE.md`.
- The main agent is a coordinator for multi-agent runs. Workers own the assigned planning artifact
  and must not modify unrelated files.
- Keep planning artifacts implementation-ready: name routes, fields, errors, IDs, transaction
  boundaries, tests, and non-goals.
- Prefer thin HTTP adapters over `personality_jelly.application`; planning must identify missing
  application service boundaries instead of moving workflow logic into `api`.
- Every planned provider-backed route must reuse Batch 08 audit/workflow/idempotency/failure
  foundations.
- If a candidate workflow cannot be specified safely, record the blocker and recommend deferring it.

## Recommended Task Order

| Task | Branch | Branch base | Depends on | Main output |
| --- | --- | --- | --- | --- |
| 01 Source Ingest API Contract | `planning/api-source-ingest-contract` | clean `dev` | Batch 08 closeout | Contract for source text/file ingest write workflow. |
| 02 Character Persona Setup API Contract | `planning/api-character-persona-contract` | clean `dev` | Batch 08 closeout | Contract for character creation, extraction, verification, and persona compilation workflow. |
| 03 Provider-Backed Write Contract Matrix | `planning/api-provider-write-contract-matrix` | integration of 01 and 02 | 01, 02 | Shared contract matrix and reconciled conventions. |
| 04 Next Implementation Batch Plan | `planning/batch-10-provider-api-implementation` | completed 03 | 03 | Implementation batch recommendation and task prompts. |
| 05 Batch 09 Closeout | `planning/batch-09-closeout` | clean `dev` after 01-04 merge | 01-04 | Planning acceptance, docs status, and next-batch handoff. |

Tasks 01 and 02 can run in parallel. Task 03 should reconcile both outputs before Task 04 writes
the implementation batch plan.

## Candidate Workflow Scope

Batch 09 should evaluate these candidates first:

- Source ingest API:
  - likely local deterministic persistence for source work/chunks;
  - may be the safest first HTTP write workflow before LLM-backed setup;
  - must still use audit, workflow run/link, idempotency, and redaction contracts.
- Character/persona setup API:
  - provider-backed candidate covering Reader extraction, Verifier validation, and persona compile;
  - must define partial persistence states for source/character/claims/evidence/persona records;
  - must link LLM traces, audit events, workflow runs, and persisted domain IDs.

Turn execution, summary generation, benchmark execution, cursor pagination migration, auth,
workspace, UI, deployment, and platform features remain out of scope for Batch 09.

## Acceptance For Batch 09

Batch 09 is complete when:

- source ingest and character/persona setup contracts are written with explicit routes,
  request/response models, status codes, redaction behavior, audit/workflow/idempotency behavior,
  persisted IDs, and failure/partial-persistence states;
- shared provider-backed write conventions are reconciled into one contract matrix;
- the next implementation batch plan and prompts are ready to execute;
- docs identify which workflow should be implemented first and why;
- no provider-backed write route or source behavior change was added during planning;
- planning artifacts, `VIBE_CODING_GUIDE.md`, and the batch plan agree on the next step.
