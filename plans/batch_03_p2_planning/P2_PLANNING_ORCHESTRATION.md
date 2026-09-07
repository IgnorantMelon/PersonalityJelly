# P2 Planning Multi-Agent Orchestration

This plan starts the first P2 phase after P1 closeout. It is a planning and audit batch, not an
implementation batch. Do not add FastAPI, web UI, platform features, graph/vector databases, new
runtime dependencies, or large service refactors from this batch unless a task explicitly documents
a small verification fix.

## Goals

- Define a clear service/API boundary for the existing CLI-first MVP.
- Audit current single-work and single-character assumptions before platform expansion.
- Design the minimum user, workspace, and audit concepts needed for later multi-user use.
- Make runtime workflow observability explicit enough for future API/UI inspection.
- Identify which CLI orchestration logic should later move into reusable application services.
- Produce P2 acceptance criteria and the recommended next implementation batch.

## Task Dependency Summary

| Task | Branch | Can start now? | Depends on | Parallel group | Main conflict risk |
| --- | --- | --- | --- | --- | --- |
| 01 FastAPI Service Boundary Design | `planning/fastapi-service-boundary` | Yes | none | Wave A | Low |
| 02 Multi-Work / Multi-Character Boundary Audit | `planning/multi-entity-boundary-audit` | Yes | none | Wave A | Low-medium |
| 03 Runtime Workflow Observability Plan | `planning/runtime-observability` | Yes | none | Wave A | Low-medium |
| 04 User / Workspace / Audit Concept Design | `planning/user-workspace-audit-model` | After 02 draft | Task 02 draft preferred | Wave B | Medium |
| 05 CLI/API Shared Service Refactor Plan | `planning/shared-service-refactor` | No | Tasks 01 and 03 | Wave C | Medium |
| 06 P2 Acceptance Criteria Snapshot | `planning/p2-acceptance-criteria` | No | Tasks 01-05 | Wave D | Low |

## Recommended Parallel Execution

### Wave A: Start Immediately

Tasks 01, 02, and 03 can run in parallel from the current `dev`.

- 01 owns the service/API boundary and should avoid deep model redesign.
- 02 owns data-boundary audit and should list risks without changing schemas.
- 03 owns workflow observability and should avoid changing trace behavior.

Each task should write a separate document instead of editing one shared P2 master document.

### Wave B: Start After Task 02 Has A Draft

Task 04 should wait until Task 02 has at least a useful draft, because user/workspace/audit
ownership depends on the current multi-work and multi-character boundary audit.

Task 04 can start before Task 02 is fully merged only if the branch author explicitly references
the draft commit or report they used.

### Wave C: Start After Tasks 01 And 03

Task 05 should wait for the service boundary and runtime observability plans. It should decide where
future reusable application services belong, but it should not perform the extraction.

Do not run Task 05 in parallel with another task that edits the same shared planning summary.

### Wave D: Final Planning Snapshot

Task 06 starts only after Tasks 01-05 are accepted and integrated. It should consolidate decisions,
define P2 completion criteria, and propose the next implementation batch.

## Coordination Rules

- Each task starts from clean `dev` and creates its own branch.
- Development agents must not merge their task branch back into `dev` at completion. They should
  commit their task changes, push the task branch to `origin`, and report the branch and commit.
- Keep this batch focused on planning, audits, and acceptance criteria.
- Avoid editing `README.md` unless the public project status becomes stale.
- Prefer writing task-specific planning docs under `plans/batch_03_p2_planning/`.
- Do not duplicate long architecture rules from `VIBE_CODING_GUIDE.md`; link back to it.
- Do not introduce keyword, regex, fixed-vocabulary, or string-containment semantic judgments.
- Do not add new dependencies or implementation modules in this batch.
- If a task discovers a real bug, document it as a P2 risk unless a tiny doc/test correction is
  required to keep the plan truthful.

## Completion Definition

Batch 03 is complete when:

- service/API boundaries are documented, including non-goals and error-model direction;
- single-work and single-character assumptions are audited with file-level references;
- user, workspace, and audit concepts have a minimum model and ownership rules;
- runtime workflow observability is mapped across turn, context, critic, memory, traces, and
  benchmark records;
- CLI-to-service extraction candidates are listed with implementation order and risk;
- P2 acceptance criteria and the first implementation batch are documented.
