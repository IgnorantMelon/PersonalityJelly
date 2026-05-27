# Task 02 Prompt: Character Persona Setup API Contract

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_09_provider_backed_api_planning/BATCH_09_PROVIDER_BACKED_API_PLANNING.md`.

## Branch

Start from clean `dev`:

```powershell
git switch dev
git status --short --branch
git switch -c planning/api-character-persona-contract
```

## Scheduling

This task can run in parallel with Task 01. It does not depend on any Batch 09 branch.

## Read First

- `README.md`
- `VIBE_CODING_GUIDE.md`
- `plans/batch_08_api_workflow_persistence/BATCH_08_CLOSEOUT.md`
- `plans/batch_06_api_write_readiness/01_write_workflow_boundary_design.md`
- `plans/batch_06_api_write_readiness/03_api_redaction_policy.md`
- `plans/batch_06_api_write_readiness/05_trace_workflow_correlation.md`
- character creation, Reader extraction, Verifier, persona compiler, and application setup services
  under `src/personality_jelly`.

## Goal

Write an implementation-ready contract for a future character/persona setup API workflow. This is
the first true provider-backed candidate and must explicitly define failure and partial-persistence
behavior before implementation.

## Output

Create:

- `plans/batch_09_provider_backed_api_planning/02_character_persona_setup_api_contract.md`

## Requirements

The contract must specify:

- candidate route names and workflow shape, such as character creation followed by setup run, or a
  single setup workflow resource;
- request fields for source work, character name/aliases, provider role bundle, workflow options,
  and explicit user/actor context;
- response fields for character, candidate claims, evidence refs, persona version, workflow summary,
  warnings, persisted IDs, and trace IDs;
- transaction boundaries across character creation, Reader extraction, Verifier validation, evidence
  persistence, persona compilation, audit events, workflow runs, and idempotency records;
- partial-persistence states for failures after source/character/claim/evidence/persona records are
  created;
- provider failure and provider validation failure behavior, including retry hints and trace IDs;
- audit event operations, workflow run/link types, and related IDs;
- redaction behavior for prompts, raw provider payloads, source text, memory-like content, local
  paths, secrets, and stack traces;
- idempotency replay/conflict policy for provider-backed workflows;
- focused application/API/storage tests needed by the implementation batch;
- explicit non-goals and deferred decisions.

## Non-Goals

- Do not implement the route.
- Do not change prompts, semantic judgment behavior, provider selection, or extraction/persona
  logic.
- Do not add turn execution, summary, benchmark, auth/workspace/platform, deployment, UI, queues, or
  external observability.

## Verification

Run:

```powershell
git diff --check
git status --short --branch
```

## Completion

Commit only this planning artifact on `planning/api-character-persona-contract`, push the branch to
`origin`, and do not merge back to `dev`.

Final report should include the route recommendation, partial-persistence model, redaction
guarantees, tests recommended for implementation, and deferred decisions.
