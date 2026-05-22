# P1 Closeout Multi-Agent Orchestration

This plan covers the remaining P1 hardening work after Tasks 01-05 have landed.
It is intentionally CLI-first and benchmark-first. Do not start P2 API, web UI,
platform, graph/vector database, or new dependency work from this plan.

## Goals

- Turn OOC and retrieval failures into curated regression assets.
- Audit and harden downstream use of layered summaries.
- Improve retrieval regression coverage without changing semantic policy by keyword rules.
- Make failed benchmark and LLM trace investigation faster from the CLI.
- Improve CLI validation diagnostics while preserving script-friendly output.
- Finish P1 with one verification pass and an updated project status snapshot.

## Task Dependency Summary

| Task | Branch | Can start now? | Depends on | Parallel group | Main conflict risk |
| --- | --- | --- | --- | --- | --- |
| 06 Benchmark Case Assets | `feature/benchmark-case-assets` | Yes | none | Wave A | Low |
| 07 Layered Summary Downstream Audit | `feature/layered-summary-downstream-audit` | Yes | none | Wave A | Medium with runtime/context work |
| 10 Trace CLI Navigation | `feature/trace-cli-navigation` | Yes | Tasks 01-05 already merged | Wave A | Medium-high in `cli/main.py` |
| 08 Retrieval Quality Regression | `feature/retrieval-quality-regression` | No | 06 merged | Wave B | Medium in retrieval benchmark tests |
| 09 OOC Regression Case Curation | `feature/ooc-regression-case-curation` | No | 06 merged | Wave B | Medium in OOC benchmark tests |
| 11 CLI Validation Diagnostics | `feature/cli-validation-diagnostics` | No | 10 merged; preferably 08 and 09 merged | Wave C | High in `cli/main.py` |
| 12 P1 Closeout Verification | `chore/p1-closeout-verification` | No | 06-11 merged | Wave D | Low |

## Recommended Parallel Execution

### Wave A: Start Immediately

Tasks 06, 07, and 10 can run in parallel from the current `dev`.

- 06 mostly establishes curated benchmark asset conventions and tests around file loading.
- 07 audits runtime/context/memory use of layered summaries.
- 10 improves trace navigation in CLI and should avoid broader CLI diagnostics changes reserved for Task 11.

Merge order within Wave A should be:

1. 06, because it unblocks regression curation.
2. 07, because it may update runtime tests but should not affect benchmark assets.
3. 10, because it touches CLI and should land before Task 11 starts.

### Wave B: Start After 06

Tasks 08 and 09 can run in parallel after 06 is merged.

- 08 owns retrieval regression case curation and retrieval benchmark assertions.
- 09 owns OOC regression case curation and OOC benchmark assertions.

They should not both edit the same JSON case files. Keep retrieval and OOC assets in separate paths.
If either task needs shared CLI output changes, stop and coordinate before editing `cli/main.py`.

### Wave C: Start After 10, Preferably After 08 and 09

Task 11 should wait for Task 10 to reduce `cli/main.py` conflicts. It can start before 08/09 if
needed, but the better sequence is after 08 and 09 so validation/error messages can cover the final
cases-file workflows.

### Wave D: Final Verification

Task 12 starts only after 06-11 are merged. It should not introduce new product behavior except
small documentation/status fixes discovered during verification.

## Coordination Rules

- Each task starts from clean `dev` and creates its own branch.
- Do not keep long-lived parallel branches touching `src/personality_jelly/cli/main.py` open at the
  same time unless the write scopes are explicitly disjoint.
- Benchmark assets are source-controlled regression data, not generated output dumps. Keep them
  small, named, reviewed, and deterministic.
- Do not add semantic keyword or regex judgments. Use structured evaluator outputs, embeddings,
  verified source evidence, or explicit test fixtures.
- Preserve stable CLI `key=value` fields. New diagnostics should append fields instead of renaming
  or removing existing fields.
- After every merge to `dev`, run at least the affected focused tests. Run full `pytest` after tasks
  that touch shared runtime, benchmark, or CLI behavior.

## Completion Definition

P1 closeout is complete when:

- curated benchmark assets exist for both retrieval and OOC workflows;
- layered summary downstream behavior is covered by focused tests;
- retrieval regression coverage includes empty-result, missing chunk, and ranking failures;
- OOC regression coverage includes observed-failure style cases outside built-in suites;
- CLI can navigate from benchmark failures to useful trace/context diagnostics;
- CLI validation errors for cases files/config/export paths are clear and stable;
- full suite passes and `VIBE_CODING_GUIDE.md` reflects the final P1 status.
