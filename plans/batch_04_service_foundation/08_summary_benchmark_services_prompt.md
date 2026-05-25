# Task 08 Prompt: Summary And Benchmark Services

Follow `VIBE_CODING_GUIDE.md`, `P2_ACCEPTANCE_CRITERIA.md`, and Batch 04 service conventions.

## Goal

Add application service wrappers for conversation summary and benchmark workflows while keeping CLI
filesystem behavior in CLI adapters.

## Scope

- Summary wrapper around `summarize_conversation`.
- OOC benchmark dry-run/run/report wrappers around existing evaluation functions.
- Retrieval benchmark dry-run/run/report wrappers around existing retrieval evaluation functions.
- Structured results for reports and case diagnostics.
- Keep JSON cases-file load/export, append, overwrite, and local path behavior CLI-only.

## Non-Goals

- Do not make benchmark execution asynchronous.
- Do not add job models.
- Do not expose filesystem paths through future API-oriented service contracts.

## Verification

Run focused summary, OOC benchmark, retrieval benchmark, and CLI benchmark tests.
