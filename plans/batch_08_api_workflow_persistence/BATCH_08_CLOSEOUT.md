# Batch 08 Closeout

Batch 08 API Workflow Persistence Foundation is closeout verified. It implements durable local
workflow persistence foundations without adding provider-backed HTTP write routes or platform
features.

## Acceptance Summary

Accepted Batch 08 outputs:

- append-only `audit_events` persistence for deterministic writes;
- `workflow_runs` and `workflow_run_links` for request/workflow/domain correlation;
- LLM trace correlation fields: `request_id`, `workflow_id`, `workflow_step`, and `related_ids`;
- durable `idempotency_records` for replay and conflict detection;
- provider failure and partial-persistence contracts with request/workflow correlation, persisted
  IDs, trace IDs, retry hints, and redacted details;
- read-only audit/workflow inspection services and routes.

Implemented write route scope remains limited to deterministic local workflows:

- `POST /conversations`
- `POST /memories/{memory_id}/review`
- `PATCH /memories/{memory_id}`
- `POST /memories/{memory_id}/archive`

Batch 08 added only read-only diagnostics routes:

- `GET /audit-events`
- `GET /audit-events/{audit_event_id}`
- `GET /workflow-runs`
- `GET /workflow-runs/{workflow_id}`

No source ingest, character/persona setup, turn execution, summary generation, benchmark execution,
provider-backed write workflow, auth/workspace feature, deployment, CORS, queue, external
observability, or UI route was added.

## Verification Summary

Verified behavior:

- deterministic domain mutations persist audit events in the same transaction;
- deterministic workflows persist workflow runs and links to domain/audit IDs;
- idempotency replay returns stored results without duplicating domain/audit/workflow rows;
- idempotency conflicts return sanitized `409 conflict` responses;
- provider failure and partial-persistence errors expose sanitized request/workflow correlation,
  persisted IDs, trace IDs, and retry hints;
- audit/workflow inspection routes are read-only, filterable, stable-ordered, and redacted;
- API handlers remain thin adapters over `personality_jelly.application`.

## Tests Run

Validation on merged `dev` before this closeout branch:

```powershell
.\.venv\Scripts\python -m pytest tests/test_storage_migrations.py tests/test_storage_schema.py tests/test_repositories.py tests/test_application_conversation_creation.py tests/test_application_memory_mutation_services.py tests/test_application_correlation.py tests/test_application_idempotency.py tests/test_application_provider_failure_contracts.py tests/test_application_audit_workflow_inspection.py tests/test_api_conversation_creation_route.py tests/test_api_memory_mutation_routes.py tests/test_api_correlation_error_envelope.py tests/test_api_audit_workflow_inspection.py tests/test_api_contract.py
```

Result: `90 passed, 15 warnings`.

```powershell
.\.venv\Scripts\python -m pytest
```

Result: `317 passed, 15 warnings`.

Warnings were SQLite datetime adapter deprecations from SQLAlchemy on Python 3.12.

## Recommended Next Batch

Recommended next batch: select and implement the first provider-backed API workflow only after its
route contract, redaction behavior, audit/workflow links, idempotency key behavior, persisted-ID
policy, and failure/partial-persistence states are explicit.

Prefer evaluating source ingest and character/persona setup before turn execution, summary
generation, benchmark execution, or cursor migration. Continue to defer auth/workspace/platform
features, CORS, deployment, UI, queues, external observability, and unrelated route expansion.
