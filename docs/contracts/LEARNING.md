# Learning Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Capture outcomes and feedback, validate evidence, apply learning policy, and maintain learning-operation provenance. Learning owns feedback interpretation/validation; Thompson owns sampling state and applies selection-state updates through its REST contract.

Learning is not a generic event bus, alerting system, or document-ranking service. Alerting/messaging remain out of initial scope unless separately approved.

## Endpoints

- POST /api/v1/learning/outcomes
- GET /api/v1/learning/operations/{operation_id}
- GET /api/v1/learning/state/{scope_id}
- GET /api/v1/learning/health and GET /api/v1/learning/ready

## Contract rules

- Each feedback event has a stable event ID, relevant selection/context reference, evidence provenance, timestamp, and policy version.
- Validation distinguishes accepted, rejected, and pending evidence. Invalid or conflicting duplicate events do not update Thompson state.
- Processing is idempotent. Same event ID and payload returns prior outcome; conflicting payload returns conflict. Retry after timeout cannot apply the update twice.
- After validation, Learning calls Thompson through REST with a stable update-event ID and explicit update semantics. It records downstream operation identity/status for restart reconciliation.
- Learning never calls Thompson implementation directly and Thompson never calls Learning. This is a one-way dependency.
- Store minimum feedback needed for audit and learning. Avoid raw prompt/response content by default; enforce retention and deletion policy.
- Record input event, validation decision/reason, policy version, downstream operation, and final status.
- Bound event size, processing time, retries, and stored evidence. Propagate request ID, deadline, and cancellation where meaningful.

## Normative outcome schema

`POST /api/v1/learning/outcomes` requires `Idempotency-Key` and fields `event_id`, `selection_id`, `context_id`, `arm_id`, `outcome`, `evidence`, `occurred_at`, and `policy_version`. Response returns `event_id`, `operation_id`, `status` (`accepted`, `rejected`, `pending`, `complete`, or `failed`), a stable `reason_code` when rejected/failed, the downstream Thompson operation identity when applicable, and `request_id`. An event is not complete until Thompson confirms the idempotent update or the operation is marked reconciliation-required.

## Endpoint status codes

- `POST /api/v1/learning/outcomes`: `202 Accepted` with operation identity after the outcome event is durably recorded; it does not wait for an unbounded downstream workflow.
- `GET /api/v1/learning/operations/{operation_id}` returns `operation_id`, event ID when known, status, optional reason code/downstream Thompson operation ID, and request ID; unknown operation returns `404 not_found`.
- `GET /api/v1/learning/state/{scope_id}` returns the opaque `scope_id`, bounded counts of accepted/rejected/pending/reconciliation-required events, and request ID; unknown scope returns `404 not_found`.
- Invalid outcome/evidence: `400 invalid_request`; conflicting idempotency payload or expected state: `409 idempotency_conflict` or `409 revision_conflict`; deadline: `504 deadline_exceeded`; Thompson unavailable: `503 dependency_unavailable` with operation status marked `reconciliation_required` when the event is already committed.

## Machine-checkable schemas

The normative Learning request/response JSON Schema is in [`schemas/learning.schema.json`](schemas/learning.schema.json). It defines outcome event fields, bounded evidence, timestamps, status values, and error envelopes.

## Errors

Use the common error envelope. Distinguish invalid event, missing selection/context, rejected evidence, duplicate event conflict, Thompson unavailable, deadline exceeded, and internal failure. A valid rejected event has explicit status rather than being confused with malformed input.

## Acceptance tests

1. Event validation and provenance are auditable.
2. Duplicate delivery does not double-apply an update; conflicting reuse fails.
3. Rejected evidence does not mutate Thompson state.
4. Thompson updates use REST only, are one-way/idempotent, and recover after restart.
5. Partial downstream failure is visible and reconciled safely.
6. Retention/privacy and required local access restrictions are enforced.
7. Event size, deadlines, retries, and status are bounded.
8. Learning does not perform retrieval ranking or generic messaging.

## Approval gate

Review with Thompson update semantics, Gateway outcome capture, provenance/retention policy, and end-to-end feedback acceptance workflows before implementation.
