# Task 04 Prompt: Batch 10 Closeout Verification

Follow `VIBE_CODING_GUIDE.md` and
`plans/batch_10_provider_backed_source_character_api/BATCH_10_PROVIDER_BACKED_SOURCE_CHARACTER_API.md`.

## Branch

Start after Tasks 01-03 are accepted and merged by the coordinator. Use clean `dev` after the
coordinator merge, or the coordinator-provided integration branch:

```powershell
git switch dev
git pull --ff-only
git switch -c chore/batch-10-source-character-api-closeout
```

If using an integration branch first, suggested name:

```powershell
git switch -c integration/batch-10-source-character-api
```

Report the actual base and integration path.

## Read First

- `VIBE_CODING_GUIDE.md`
- `plans/batch_10_provider_backed_source_character_api/BATCH_10_PROVIDER_BACKED_SOURCE_CHARACTER_API.md`
- `plans/batch_09_provider_backed_api_planning/03_provider_backed_write_contract_matrix.md`
- Task 01, 02, and 03 commits
- `README.md`
- current API route files and application service files

## Goal

Verify and document Batch 10. This task should not add new route behavior except for narrow fixes
required to make the accepted Batch 10 implementation pass closeout.

## Closeout Checks

Route scope:

- Confirm Batch 10 added exactly:
  - `POST /source-works`
  - `POST /characters`
- Confirm it did not add:
  - `POST /characters/{character_id}/persona-setup-runs`
  - `POST /character-persona-setup-runs`
  - `POST /source-ingestions`
  - upload, URL, embeddings, turn, summary, benchmark, auth/workspace, UI, deployment, queue, or
    cursor routes.

Application/API boundary:

- Confirm API handlers call application services and shared write helpers.
- Confirm route handlers do not call extraction, persona, provider, repository, semantic, prompt,
  or retrieval modules directly.
- Confirm CLI `ingest_text_file` behavior remains unchanged.

Audit/workflow/idempotency:

- Confirm `source_work.ingest` persists source work, chunks, audit event, workflow run, workflow
  links, and idempotency replay as expected.
- Confirm `character.create` persists character, audit event, workflow run, workflow links, and
  optional idempotency replay as expected.
- Confirm source ingest replay does not duplicate source work/chunks/audit/workflow/link rows.
- Confirm character create replay does not duplicate character/audit/workflow/link rows when an
  idempotency key is supplied.
- Confirm workflow links use Task 03 relation names: `input`, `created`, `audit`, and
  `idempotency`.

Redaction:

- Confirm write responses and error envelopes never expose raw source content, chunk text, source
  previews, local paths, path-like metadata values, provider config, prompts, raw provider payloads,
  SQL, stack traces, secrets, auth headers, or raw request bodies.
- Confirm audit/workflow inspection routes expose safe diagnostics only.
- Confirm OpenAPI schemas do not expose local path fields, provider config, prompt controls, raw
  outputs, or debug-only payloads.

Deferred persona setup:

- Confirm provider-backed persona setup remains unimplemented.
- Add a concise handoff section to the closeout artifact for the later
  `POST /characters/{character_id}/persona-setup-runs` batch, grounded in Task 03 and the actual
  Batch 10 implementation state.

## Tests

Run focused Batch 10 tests:

```powershell
.\.venv\Scripts\python -m pytest tests/test_application_source_ingest_workflow.py tests/test_api_source_ingest_route.py tests/test_application_character_creation_workflow.py tests/test_api_character_creation_route.py
```

Run shared regression tests:

```powershell
.\.venv\Scripts\python -m pytest tests/test_storage_migrations.py tests/test_storage_schema.py tests/test_repositories.py tests/test_application_correlation.py tests/test_application_idempotency.py tests/test_application_audit_workflow_inspection.py tests/test_api_correlation_error_envelope.py tests/test_api_audit_workflow_inspection.py tests/test_api_contract.py
```

Run full suite:

```powershell
.\.venv\Scripts\python -m pytest
```

If the full suite fails for an unrelated environmental reason, capture the exact failing command,
failure summary, and why it is believed unrelated. Do not hide failures.

## Documentation

Create:

- `plans/batch_10_provider_backed_source_character_api/BATCH_10_CLOSEOUT.md`

Update `README.md` and `VIBE_CODING_GUIDE.md` only if Batch 10 has been accepted and the current
status needs to reflect the newly implemented routes. Keep `README.md` public-facing and concise;
keep agent workflow and implementation guidance in `VIBE_CODING_GUIDE.md`.

The closeout artifact must include:

- branch and commit integration order;
- route scope implemented;
- application services added;
- storage/migration status;
- audit/workflow/idempotency behavior verified;
- redaction behavior verified;
- focused and full test results;
- known caveats;
- deferred persona setup handoff and recommended next batch.

## Non-Goals

- Do not implement persona setup as part of closeout.
- Do not add new routes beyond narrow fixes for accepted Batch 10 scope.
- Do not add migrations, provider behavior, semantic changes, prompt changes, auth/workspace,
  deployment, UI, queues, uploads, URL fetches, embeddings, or cursor migration.

## Completion

Run:

```powershell
git diff --check
git status --short --branch
```

Commit closeout documentation and any accepted narrow fixes. Push the branch and report branch,
commit hash, tests run, route scope, closeout status, and deferred work.
