# Audit Readiness Decision

Task: `plans/batch_04_service_foundation/10_audit_readiness_prompt.md`

## Decision

Batch 04 keeps audit persistence design-only and does not add a physical audit table.

Reasoning:

- Manual memory review/edit/archive are still CLI-only repository operations in this batch.
- No API/UI adapter exists yet to enforce actor context, request IDs, or permission boundaries.
- Adding a schema migration at the end of the service-foundation batch would make storage policy
  decisions before the first API-facing write services exist.

The implemented readiness layer is therefore a strict application payload model:

- `AuditActor`
- `AuditEntity`
- `AuditRelatedIds`
- `AuditEventPayload`
- manual memory event builders for review, edit, and archive

`AuditEventPayload.persistence` is fixed to `payload_only` for Batch 04. Future Batch 05+ work can
persist the same payload shape in an append-only table.

## Minimum Manual Memory Contract

Before manual memory operations move from CLI-only repository calls into API/UI-facing application
services, callers must provide:

- actor type and actor ID;
- operation name;
- affected memory ID;
- reason, including archive reason;
- related `user_id`, `character_id`, and optional `conversation_id`;
- before and after snapshots containing memory scope, status, content, importance, and reason.

The memory audit builders validate that before/after snapshots preserve the same memory identity,
user, character, conversation, and scope. Audit payloads explain the mutation; the memory row remains
the source of current state.

## Deferred

- Physical audit table and repository.
- Workspace/member/auth fields beyond optional payload shape.
- Audit retention/export/compliance behavior.
- Full tracing foreign-key migration for `LLMRawOutput`.
- Auditing every domain transition.

## Verification

This task adds transport-neutral payload code and tests. No schema migration is included.
