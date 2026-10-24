# Thompson Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Own Thompson-sampling state and selection semantics: arm/option identity, context/profile, exposure counts, reward evidence references, posterior/state updates, and selection provenance. This is decision selection, not document relevance Ranking.

## Endpoints

- POST /api/v1/thompson/selections: select an option for a context.
- POST /api/v1/thompson/updates: apply a validated reward/update event idempotently.
- GET /api/v1/thompson/state/{context_id}: inspect a bounded state summary subject to required local access restrictions; encode `context_id` as one path segment.
- GET /api/v1/thompson/health and GET /api/v1/thompson/ready.

## Semantics

- Selection request identifies a versioned policy, context, eligible arms, and optional exploration constraints. The service returns chosen arm, policy/state version, and bounded explanation/provenance.
- Eligible arms are validated; the service cannot choose an arm excluded by caller policy. Caller policy is a selection constraint, not an identity assertion.
- Update events have stable event IDs and idempotency. Duplicate delivery must not double-count reward or exposure. Updates referencing unknown arms/context are explicit failures.
- Reward evidence records source/event identity, timestamp, validation status, and applicable policy version. The service stores decision state, not raw sensitive prompt content by default.
- Concurrency semantics for selection/update are explicit. State versions support conflict detection and audit. Recovery preserves committed state.
- Learning owns feedback validation/outcome interpretation; it calls Thompson through REST to apply approved updates. Thompson does not call Learning, preventing a cycle. Gateway may call Thompson through REST for selection.
- Do not conflate Thompson scores/probabilities with retrieval relevance scores.

## Normative request/response fields

`POST /api/v1/thompson/selections` requires `Idempotency-Key`, `context_id`, `policy` (`name` and `version`), `eligible_arms`, and optional `expected_state_version`. Each arm has a stable `arm_id` and optional context features. Response returns `selection_id`, `chosen_arm_id`, `policy`, `state_version`, bounded `evidence`, and `request_id`.

`POST /api/v1/thompson/updates` requires `Idempotency-Key`, stable `event_id`, `context_id`, `arm_id`, validated reward value/semantics, evidence reference, and optional `expected_state_version`. Response returns `event_id`, `operation_id`, `applied`, resulting `state_version`, and `request_id`. Conflicting state versions return `409 revision_conflict`; duplicate event IDs with identical payload return the original result.

## Machine-checkable schemas

The normative Thompson request/response JSON Schema is in [`schemas/thompson.schema.json`](schemas/thompson.schema.json). It defines selection, update, and response field types, bounds, and state-version conflicts.

## Errors

Use the common error envelope. Distinguish invalid context/policy, no eligible arms, unknown arm, duplicate event with conflicting payload, state version conflict, unauthorized state access, deadline exceeded, and internal failure. No eligible arm is not silently converted into an arbitrary choice.

## Acceptance tests

1. Same selection inputs and state/policy version have documented reproducibility semantics.
2. Excluded arms are never selected.
3. Duplicate update event does not double-count; conflicting reuse of event ID fails.
4. Reward update provenance and state version are observable.
5. Concurrent updates and restart recovery preserve invariants.
6. Learning-to-Thompson and Gateway-to-Thompson calls use REST only.
7. Thompson does not call Learning or retrieval services.
8. State access applies required local access restrictions and sensitive payloads are not logged.
9. Thompson output is clearly distinct from relevance ranking.

## Approval gate

Review with Learning feedback validation, Gateway selection workflows, persistence/recovery, policy versioning, and acceptance tests before implementation.
