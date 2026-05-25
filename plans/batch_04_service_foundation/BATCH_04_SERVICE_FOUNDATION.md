# Batch 04 Service Foundation

Batch 04 is the first implementation batch after P2 planning. Its purpose is to extract a reusable
application-service foundation behind the existing CLI so a later FastAPI adapter can be thin and
low-risk.

Do not add FastAPI, web UI, auth, workspace, external graph/vector databases, LangGraph,
third-party memory frameworks, or new runtime dependencies in this batch unless a task is updated
and accepted by maintainers.

## Batch Goals

- Create a thin `personality_jelly.application` service layer for shared orchestration.
- Preserve CLI behavior and stable `key=value` diagnostics.
- Move read-only inspection assembly out of CLI printing code.
- Make turn and benchmark workflow results carry the IDs needed for API/UI inspection.
- Keep semantic judgment in existing model-backed modules.
- Leave future HTTP handlers as adapters over the new services.

## Shared Guardrails

- Start each task from clean `dev` and use a scoped branch.
- Keep changes small and focused; avoid formatting churn.
- Do not change storage schemas unless a task explicitly asks for a migration.
- Do not move prompts or structured semantic schemas into the application layer.
- Do not import CLI modules from application services or future API code.
- Preserve existing CLI output by default. Additive diagnostics must be documented and tested.
- Run focused tests for touched behavior, then the full suite before implementation closeout.

## Recommended Task Order

| Task | Branch | Can start | Depends on | Main output |
| --- | --- | --- | --- | --- |
| 01 Application Bootstrap Foundation | `feature/application-bootstrap` | Immediately | none | Application package, database/session/provider bundles, basic error normalization. |
| 02 Inspection Result Models | `feature/inspection-result-models` | After 01 draft | 01 | Shared result dataclasses/Pydantic models and conventions. |
| 03 Conversation And Context Inspection | `feature/conversation-context-inspection` | After 02 | 02 | Conversation, messages, summary layers, context package expansion service. |
| 04 Character Claim Memory Inspection | `feature/character-memory-inspection` | After 02 | 02 | Character, claims/evidence, memories, source chunk detail services. |
| 05 Critic Trace Eval Inspection | `feature/critic-trace-eval-inspection` | After 02 | 02 | Critic, failure case, LLM trace, OOC eval, retrieval eval inspection services. |
| 06 CLI List/Show Migration | `feature/cli-inspection-services` | After 03-05 | 03, 04, 05 | CLI list/show commands consume inspection services with compatibility tests. |
| 07 Turn Workflow Service | `feature/turn-workflow-service` | After 01 and 03 | 01, 03 | Structured turn service result with complete IDs, CLI turn compatibility. |
| 08 Summary And Benchmark Services | `feature/summary-benchmark-services` | After 01 and 05 | 01, 05 | Summary and benchmark wrappers, CLI cases-file behavior preserved. |
| 09 Character Persona Setup Service | `feature/character-persona-setup-service` | After 01 and 04 | 01, 04 | Reusable character/persona setup sequence, demo reuse stays CLI-only. |
| 10 Audit Readiness Spike | `feature/audit-readiness` | After 07 | 04, 07 | Audit payload/table decision for manual memory operations. |

Tasks 03, 04, and 05 can run in parallel after Task 02 establishes result conventions. Tasks 07 and
08 can run in parallel after their dependencies merge. Task 09 should stay late because it touches
the broad demo setup path.

## Acceptance For Batch 04

Batch 04 is complete when:

- The application layer exists and is documented.
- CLI list/show command families call inspection services without losing existing diagnostics.
- Turn workflow service returns complete inspection IDs, including created memory IDs.
- Benchmark and summary wrappers exist or are explicitly deferred with documented blockers.
- Focused CLI/runtime/evaluation tests pass for touched commands.
- Full test suite passes before final merge.
- No new public API surface, web UI, or platform features were introduced.

## Deferred To Batch 05 Or Later

- FastAPI handlers and route models.
- Authentication, actor identity beyond local/synthetic actor context, permissions, and workspace.
- Physical audit table if Batch 04 only completes an audit payload design.
- Trace schema migration for first-class foreign keys.
- Multi-work canon policies and multi-character conversation models.
