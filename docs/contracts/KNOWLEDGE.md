# Knowledge Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Own durable sourced knowledge records, source identity/revisions, lifecycle/status, provenance, scope, and direct canonical lookup. Knowledge distinguishes sourced claims/material from episodic memory; exact taxonomy and overlap rules with Memory must be finalized before implementation.

Knowledge owns canonical records; Index owns derived searchable representations. Knowledge initiates ingestion/update/delete and calls Chunking, Tokenization, Embedding when required, and Index through REST only.

## Endpoints

All mutating create/update/delete operations return `202 Accepted` after canonical commit and return an `operation_id`; they never wait synchronously for Index or Graph completion. `GET` reads and verification return `200 OK`; invalid JSON/schema returns `400`; semantic/profile/size validation returns `422` (`source_too_large` for a source exceeding the resolved profile); stale expected base revision returns `409 revision_conflict`; missing record/operation returns `404`; expired idempotency key returns `409 idempotency_key_expired`; deadline exceeded before canonical commit returns `504 deadline_exceeded`; failures after canonical commit are visible in operation status.

- POST /api/v1/knowledge/sources
- GET /api/v1/knowledge/sources/{source_id}
- POST /api/v1/knowledge/sources/{source_id}/revisions
- DELETE /api/v1/knowledge/sources/{source_id}
- POST /api/v1/knowledge/sources/revisions/verify: batch-verify candidate source IDs and revision sequences for Gateway freshness checks.
- GET /api/v1/knowledge/sources/{source_id}/operations/{operation_id}
- GET /api/v1/knowledge/health and GET /api/v1/knowledge/ready
- GET /api/v1/knowledge/reconciliation/manifest: paginated manifest of active canonical revisions and tombstones, with stable snapshot/cursor semantics.
- POST /api/v1/knowledge/reconciliation: start or resume owner-scoped reconciliation/rebuild into a specified Index generation; return a durable operation ID and status.

## Contract rules

- Every source has stable identity, owner/scope, source kind, canonical locator where applicable, revision, provenance, lifecycle status, and retention/deletion policy.
- Revisions are immutable snapshots with an opaque revision ID, monotonically increasing per-source revision_sequence, and capture time. The current revision is unambiguous; updates do not silently mutate historical evidence. Revision updates supply `expected_base_revision_sequence`; if it does not match the active sequence, return `409 revision_conflict` rather than silently applying last-write-wins.
- Preserve provenance to original source, source revision, and extraction/normalization profile. Distinguish source facts from derived interpretations.
- Mutations are idempotent; same key with a different payload conflicts. Any local access restrictions required by the deployment are enforced server-side; scope remains a partition filter.
- Delete durably tombstones the canonical source first, allocating a new monotonic `revision_sequence`, and immediately blocks direct lookup. It then submits idempotent Index and Graph source-deletion operations carrying that sequence. Report delete complete only after Index and Graph confirm all derived representations are retrieval-ineligible; otherwise report pending/reconciliation-required. While pending, Gateway verifies candidate existence/current revision against Knowledge before exposing candidates as current; if verification is unavailable, fail closed for those candidates. Index rejects upserts at or below the received tombstone sequence. Tombstone high-water marks survive operation-record expiry and rebuilds.
- Ingestion durably records source revision and operation identity, then calls Chunking, Tokenization, Embedding as required, and Index via REST. Where the source yields explicit relationships, Knowledge also submits a provenance-bearing source projection to Graph over REST. Before canonical commit, validate that the complete derived representation fits the active Index profile's source limits; reject oversized input before commit. Track stage status and support retry/reconciliation after restart. Canonical source revision remains authoritative if indexing fails.
- Source persistence and Index publication are not one distributed transaction. Long-running ingestion returns `202 Accepted` with a durable operation ID when it cannot complete within the request deadline or inline limits.
- Knowledge provides canonical lookup. Generic lexical/vector candidate search belongs to retrieval services over Index and is orchestrated by Gateway; Knowledge must not duplicate generic corpus search.

## Owner-led reconciliation and recovery

Knowledge owns enumeration and replay of its own canonical sources; Index never calls Knowledge. The paginated manifest contains active revision IDs/sequences, scope, required profile identity, and tombstone high-water marks, pinned to a stable snapshot. Reconciliation stages current representations and tombstones into the requested Index generation, replays changes newer than the snapshot, and reports complete only when no mutation remains unreplayed. Repeated operations are idempotent and restartable. Operators/Gateway trigger Knowledge and Memory reconciliation independently.

## Normative write schemas

Create `POST /api/v1/knowledge/sources` requires `Idempotency-Key` and JSON fields `scope`, `source_kind`, `canonical_locator` where applicable, `content`, `provenance`, `retention_policy`, and `index_profile`. Response is `201` when canonical creation and required inline indexing complete, or `202` with `operation_id`, `source_id`, `revision`, `revision_sequence`, and `status` when indexing remains pending.

Revision update `POST /api/v1/knowledge/sources/{source_id}/revisions` requires `Idempotency-Key`, `expected_base_revision_sequence`, new `content`, `provenance`, and effective `index_profile`. A stale base sequence returns `409 revision_conflict`. Response carries `source_id`, opaque `revision`, new `revision_sequence`, `operation_id`, and `status`.

Delete `DELETE /api/v1/knowledge/sources/{source_id}` requires a stable idempotency key and explicit delete scope. Response contains `source_id`, tombstone `revision_sequence`, `operation_id`, and `status` (`pending`, `complete`, or `reconciliation_required`). Canonical lookup is blocked as soon as the tombstone commits, even while Index reconciliation is pending.

The freshness endpoint accepts 1–100 `{source_id, revision_sequence}` items and returns one result per input: `current`, `stale`, `tombstoned`, or `not_found`, with the canonical current sequence when safe. It does not return source content. Gateway uses this batch endpoint before exposing candidates.

Reconciliation manifests return `snapshot_id`, a durable `change_cursor`, `next_cursor` (null at end), and bounded `items`. Knowledge retains a durable mutation journal after that cursor and replays every later create/update/tombstone to the target Index generation until caught up; the final caught-up watermark is returned to Index for cutover validation. each item includes `source_id`, active revision/sequence or tombstone sequence, `scope`, and `index_profile`. The owner reconciliation operation requires `Idempotency-Key`, `snapshot_id`, and `target_generation`, and returns `operation_id` and `status`.

## Errors and acceptance tests

Use the common error envelope. Distinguish invalid source, unauthorized scope, revision/idempotency conflict, retention/deletion restriction, dependency unavailable, indexing pending/failed, deadline exceeded, and internal failure. Test immutable revisions, provenance, authorization, deletion/stale-write prevention, REST-only dependencies, partial failure/reconciliation, canonical availability during Index outage, no duplicate retrieval logic, bounded retries, privacy, and restart recovery.

## Change-journal seal for Index cutover

Knowledge exposes `POST /api/v1/knowledge/reconciliation/seal` and `POST /api/v1/knowledge/reconciliation/seal/{seal_id}/release`. Seal durably fences new canonical commits, returns a final owner-wide `change_cursor`, and remains active across process restart until explicit release. Mutations arriving during the seal may be queued but are not acknowledged as committed until release. Knowledge's reconciliation manifest and journal are replayed to the target generation through the sealed cursor. If Knowledge is unavailable, Index cutover cannot proceed. A sequence counter restored below the maximum Index high-water mark is detected before accepting writes; Knowledge enters `sequence_recovery_required` and reconciles the next sequence from Index status before resuming.

## Approval gate

Review with Memory, Index, Chunking, Tokenization, Embedding, Gateway, source/provenance policy, and end-to-end ingestion/retrieval workflows before implementation.
