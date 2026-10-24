# Thompson Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Own Thompson-sampling state and selection semantics: arm/option identity, context/profile, exposure counts, reward evidence references, posterior/state updates, and selection provenance. This is decision selection, not document relevance Ranking.

## Endpoints

- POST /api/v1/thompson/selections: select an option for a context.
- POST /api/v1/thompson/updates: apply a validated reward/update event idempotently.
- GET /api/v1/thompson/state/{context_id}: inspect safe state summary under authorization.
- GET /api/v1/thompson/health and GET /api/v1/thompson/ready.

## Semantics

- Selection request identifies a versioned policy, context, eligible arms, and optional exploration constraints. The service returns chosen arm, policy/state version, and bounded explanation/provenance.
- Eligible arms are validated; the service cannot choose an arm excluded by caller policy. Caller policy itself is not authorization.
- Update events have stable event IDs and idempotency. Duplicate delivery must not double-count reward or exposure. Updates referencing unknown arms/context are explicit failures.
- Reward evidence records source/event identity, timestamp, validation status, and applicable policy version. The service stores decision state, not raw sensitive prompt content by default.
- Concurrency semantics for selection/update are explicit. State versions support conflict detection and audit. Recovery preserves committed state.
- Learning owns feedback validation/outcome interpretation; it calls Thompson through REST to apply approved updates. Thompson does not call Learning, preventing a cycle. Gateway may call Thompson through REST for selection.
- Do not conflate Thompson scores/probabilities with retrieval relevance scores.

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
8. State access is authorized and sensitive payloads are not logged.
9. Thompson output is clearly distinct from relevance ranking.

## Approval gate

Review with Learning feedback validation, Gateway selection workflows, persistence/recovery, policy versioning, and acceptance tests before implementation.
