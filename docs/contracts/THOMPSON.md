# Thompson Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Own Thompson-sampling state and selection semantics: arm/option identity, context/profile, exposure counts, reward evidence references, posterior/state updates, and selection provenance. This is decision selection, not document relevance Ranking.

## Endpoints

- POST /api/v1/thompson/selections: select an option for a context.
- POST /api/v1/thompson/updates: apply a validated reward/update event idempotently.
- GET /api/v1/thompson/state/{context_id}: inspect a bounded state summary `{context_id, state_version, arms, request_id}` subject to required local access restrictions; each arm includes `arm_id`, exposure count, reward count, and nullable mean reward. Encode `context_id` as one path segment.
- GET /api/v1/thompson/health and GET /api/v1/thompson/ready.

## Semantics

- V1 selection policy is `beta-bernoulli-v1` version `1`, with Beta(1,1) prior for each arm and binary rewards only (`0` or `1`). The first selection for an unseen `context_id` initializes context state at `state_version=0`; each eligible arm not yet present is initialized with prior alpha=1, beta=1. Selection draws one Beta sample per eligible arm using the configured versioned PRNG/seed policy, then chooses the highest sample; ties use `arm_id` Unicode code-point ascending. The response records policy, state version, and a non-sensitive selection audit reference. A different prior, reward model, or PRNG policy requires a new policy version and fixtures.
- Eligible arms are validated; the service cannot choose an arm excluded by caller policy. Caller policy is a selection constraint, not an identity assertion.
- Update events have stable event IDs and idempotency. V1 accepts reward values only in `{0,1}` under `beta-bernoulli-v1`; reward 1 increments alpha by one and reward 0 increments beta by one. Duplicate delivery must not double-count reward or exposure. Updates referencing unknown arms/context are explicit failures.
- Reward evidence records source/event identity, timestamp, validation status, and applicable policy version. The service stores decision state, not raw sensitive prompt content by default.
- Every context has a monotonic integer `state_version`. A request with `expected_state_version` must match the current version or returns `409 revision_conflict`; successful state mutation increments it by exactly one. Same `event_id` and canonical payload returns the original result without incrementing again; same event ID with a different payload returns `409 idempotency_conflict`. A selection is idempotent for the same `Idempotency-Key` and canonical payload: retries return the persisted selection and do not draw again. Different idempotency keys may produce different valid samples even with the same eligible arms and state version; v1 does not promise cross-implementation bit-for-bit sampling reproducibility. The response records the state version used and the policy version. Recovery preserves committed state.
- Learning owns feedback validation/outcome interpretation; it calls Thompson through REST to apply approved updates. Thompson does not call Learning, preventing a cycle. Gateway may call Thompson through REST for selection.
- Do not conflate Thompson scores/probabilities with retrieval relevance scores.

## Normative request/response fields

`POST /api/v1/thompson/selections` requires `Idempotency-Key`, `context_id`, `policy` (`name:"beta-bernoulli-v1"`, `version:"1"`), `eligible_arms`, and optional `expected_state_version`. Each arm has a stable `arm_id` and optional context features. Response returns `selection_id`, `chosen_arm_id`, `policy`, `state_version`, bounded `evidence`, and `request_id`.

`POST /api/v1/thompson/updates` requires `Idempotency-Key`, stable `event_id`, `context_id`, `arm_id`, `reward` exactly `0` or `1`, `reward_semantics:"binary"`, evidence reference, and optional `expected_state_version`. Response returns `event_id`, `operation_id`, `applied`, resulting `state_version`, and `request_id`. Conflicting state versions return `409 revision_conflict`; duplicate event IDs with identical payload return the original result.

## Endpoint status codes

- Selection and update success: `200` with the documented result.
- Invalid context/policy/arm/reward: `400 invalid_request` or `422 unsupported_profile`.
- Unknown context/arm: `404 not_found`; stale state version or conflicting idempotency payload: `409 revision_conflict` or `409 idempotency_conflict`.
- No eligible arms: `422 no_eligible_arms`.
- Deadline: `504 deadline_exceeded`; unavailable state store: `503 service_unavailable`.

## Machine-checkable schemas

The normative Thompson request/response JSON Schema is in [`schemas/thompson.schema.json`](schemas/thompson.schema.json). It defines selection, update, and response field types, bounds, and state-version conflicts.

## Errors

Use the common error envelope. Distinguish invalid context/policy, no eligible arms, unknown arm, duplicate event with conflicting payload, state version conflict, required local access restriction failure, deadline exceeded, and internal failure. No eligible arm is not silently converted into an arbitrary choice.

## Acceptance tests

1. Repeating the same selection payload and `Idempotency-Key` returns the same persisted choice; a new key is a new stochastic selection and cannot mutate state merely by selecting.
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
