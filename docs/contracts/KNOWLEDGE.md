# Knowledge Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Own durable sourced knowledge records, source identity/revisions, lifecycle/status, provenance, scope, and direct canonical lookup. Knowledge distinguishes sourced claims/material from episodic memory; exact taxonomy and overlap rules with Memory must be finalized before implementation.

Knowledge owns canonical records; Index owns derived searchable representations. Knowledge initiates ingestion/update/delete and calls Chunking, Tokenization, Embedding when required, and Index through REST only.

## Endpoints

- POST /api/v1/knowledge/sources
- GET /api/v1/knowledge/sources/{source_key}
- POST /api/v1/knowledge/sources/{source_key}/revisions
- DELETE /api/v1/knowledge/sources/{source_key}
- POST /api/v1/knowledge/sources/verify-revisions: batch-verify candidate source IDs and revision sequences for Gateway freshness checks. Request body is `{items:[{source_id,revision_sequence}],request_id}`; only `knowledge:` IDs are accepted. Response body is `{results:[{source_id,requested_revision_sequence,status,canonical_revision_sequence?}],request_id}`, where status is `current`, `stale`, `tombstoned`, or `not_found`.
- GET /api/v1/knowledge/sources/{source_key}/operations/{operation_id}
- GET /api/v1/knowledge/operations/{operation_id}: report canonical commit and indexing status.
- GET /api/v1/knowledge/health and GET /api/v1/knowledge/ready
- GET /api/v1/knowledge/reconciliation/manifest: paginated manifest of active canonical revisions and tombstones, with stable snapshot/cursor semantics.
- POST /api/v1/knowledge/reconciliation: start or resume owner-scoped reconciliation/rebuild into a specified Index generation; return a durable operation ID and status.
- POST /api/v1/knowledge/reconciliation/fence: acquire a short-lived canonical-write fence for a reconciled target generation.
- POST /api/v1/knowledge/reconciliation/fence/release: idempotently release a fence after cutover or an aborted attempt.

## Contract rules

- Every source has a stable opaque `source_key` matching `[A-Za-z0-9._~-]{1,128}`; its Index source ID is `knowledge:<source_key>`; `source_key` is only the opaque suffix. Canonical locators are separate metadata and MUST NOT be embedded in source IDs. Every source also has owner/scope, source kind, canonical locator where applicable, revision, provenance, lifecycle status, and retention/deletion policy.
- Revisions are immutable snapshots with an opaque revision ID, monotonically increasing per-source revision_sequence, and capture time. The current revision is unambiguous; updates do not silently mutate historical evidence. Revision updates supply `expected_base_revision_sequence`; if it does not match the active sequence, return `409 revision_conflict` rather than silently applying last-write-wins.
- Preserve provenance to original source, source revision, and extraction/normalization profile. Distinguish source facts from derived interpretations.
- Mutations are idempotent; same key with a different payload conflicts. Any local access restrictions required by the deployment are enforced server-side; scope remains a partition filter.
- Delete durably tombstones the canonical source first, allocating a new monotonic `revision_sequence`, and immediately blocks direct lookup. It then submits idempotent Index and Graph source-deletion operations carrying that sequence. Report delete complete only after Index and Graph confirm all derived representations are retrieval-ineligible; otherwise report pending/reconciliation-required. While pending, Gateway verifies candidate existence/current revision against Knowledge before exposing candidates as current; if verification is unavailable, fail closed for those candidates. Index rejects upserts at or below the received tombstone sequence. Tombstone high-water marks survive operation-record expiry and rebuilds.
- Ingestion durably records source revision and operation identity, then calls Chunking, Tokenization, Embedding as required, and Index via REST. Where the source yields explicit relationships, Knowledge also submits a provenance-bearing source projection to Graph over REST. Before canonical commit, validate that the complete derived representation fits the active Index profile's source limits; reject oversized input before commit. Track stage status and support retry/reconciliation after restart. Canonical source revision remains authoritative if indexing fails.
- Source persistence and Index publication are not one distributed transaction. In v1, ingestion always returns `202 Accepted` with a durable operation ID after bounded preflight and canonical commit; it never waits inline for derived work.
- Knowledge provides canonical lookup. Generic lexical/vector candidate search belongs to retrieval services over Index and is orchestrated by Gateway; Knowledge must not duplicate generic corpus search.

## Owner-led reconciliation and recovery

Knowledge owns enumeration and replay of its own canonical sources; Index never calls Knowledge. The paginated manifest contains active revision IDs/sequences, scope, required profile identity, and tombstone high-water marks, pinned to a stable snapshot. Reconciliation stages current representations and tombstones into the requested Index generation, replays changes newer than the snapshot, and reports complete only when no mutation remains unreplayed. Repeated operations are idempotent and restartable. Operators/Gateway trigger Knowledge and Memory reconciliation independently.

## Normative write schemas

Create `POST /api/v1/knowledge/sources` requires `Idempotency-Key` and JSON fields `scope`, `source_kind`, `canonical_locator` where applicable, `content`, `provenance`, `retention_policy`, and `index_profile`. Before canonical commit, Knowledge resolves the requested `index_profile` through `GET /api/v1/index/profiles/{profile_name}/versions/{profile_version}` and validates the returned digest. It then makes one bounded REST preflight call to Chunking to determine the complete chunk count and encoded representation bound under the resolved bundle. The preflight is capped at 500 ms and must not perform Tokenization, Embedding, Index, or Graph work. If preflight times out, no canonical mutation is committed and the endpoint returns `504 deadline_exceeded`; if limits are exceeded, return `422 source_too_large`. After preflight and canonical commit, response is always `202 Accepted` with `operation_id`, `source_id`, `revision`, `revision_sequence`, `status`, and `indexing_status=pending_index`. No downstream derived work is awaited after canonical commit.

Revision update `POST /api/v1/knowledge/sources/{source_key}/revisions` requires `Idempotency-Key`, `expected_base_revision_sequence`, new `content`, `provenance`, and effective `index_profile`. A stale base sequence returns `409 revision_conflict`. Response carries `source_id`, opaque `revision`, new `revision_sequence`, `operation_id`, `status`, and `indexing_status`.

Delete `DELETE /api/v1/knowledge/sources/{source_key}` requires a stable idempotency key and `delete_scope=source`. Response contains `source_id`, tombstone `revision_sequence`, `operation_id`, `status`, `indexing_status`, and `graph_status`. Canonical lookup is blocked as soon as the tombstone commits. `status=complete` is permitted only after Index confirms the tombstone is durable and retrieval-ineligible in the active generation AND Graph confirms every fact supported by this source is retrieval-ineligible. Until both confirmations arrive, status remains `pending` or `reconciliation_required`; physical cleanup may continue asynchronously.

The freshness endpoint accepts 1–100 `{source_id, revision_sequence}` items and returns one result per input: `current`, `stale`, `tombstoned`, or `not_found`, with the canonical current sequence when safe. It does not return source content. Both Memory and Knowledge use the same request/response shape; Knowledge additionally validates that each `source_id` has the `knowledge:` owner prefix.

Reconciliation manifests return `snapshot_id`, a durable `change_cursor`, `next_cursor` (null at end), and bounded `items`. Knowledge retains a durable mutation journal after that cursor and replays every later create/update/tombstone to the target Index generation until caught up; the final caught-up watermark is returned to Index for cutover validation. Each item includes `source_id`, active revision/sequence or tombstone sequence, `scope`, and `index_profile`. The owner reconciliation operation requires `Idempotency-Key`, `snapshot_id`, and `target_generation`, and returns `operation_id` and `status`.

## Graph projection journal

Knowledge maintains a separate durable monotonically increasing `owner_projection_sequence` for each Graph projection/deletion event, independent of canonical `revision_sequence`. Each event is submitted to Graph over REST with that sequence and a stable idempotency/operation identity. After restart or Graph-store recovery, Knowledge replays the durable Graph journal in sequence order. Once all events through sealed sequence W are acknowledged, Knowledge posts `{owner: knowledge, sealed_projection_sequence: W, request_id}` to `POST /api/v1/graph/reconciliation/checkpoints`; Graph must report the contiguous applied sequence and readiness. Knowledge never assumes Graph recovery from the largest source revision alone.

## Source identity and path encoding

Knowledge source IDs have the grammar `knowledge:<opaque-owner-id>`, where the suffix matches `[A-Za-z0-9._~-]{1,128}`. The suffix is generated, immutable, owner-assigned, and MUST NOT be the canonical locator or derived from locator text. Every operation ID is namespaced `knowledge:op:<opaque-id>` so Gateway can route `after_operation_id` without guessing. Owner-local resource paths use `{source_key}` for the suffix only; service-to-service payloads and verification use the full namespaced `source_id`. Gateway routes by the exact `knowledge:` prefix, removes that prefix once, and percent-encodes the remaining suffix as one RFC 3986 path segment. A deleted locator restored as a new source creates a new opaque `source_id` by default. Only an explicit restoration of the same logical source may reuse its tombstoned `source_id`, and only with a `revision_sequence` strictly greater than the tombstone high-water mark. A source ID is never reassigned to a different logical source. After backup restore, Knowledge remains not-ready for writes until it enumerates its local canonical source manifest and paginates `GET /api/v1/index/sources/manifest?owner=knowledge`. Reconcile the union, not only IDs still present locally: any Index identity absent from the restored canonical manifest or any Index high-water mark above the local canonical sequence blocks readiness. The owner requires operator-directed canonical recovery or a new tombstone; incrementing a counter cannot reconstruct lost content. For known IDs, also compare per-source Index status. Any sequence regression returns `409 revision_sequence_regression`. Knowledge queries Index over REST; Index never calls Knowledge. Never interpolate a raw locator into a route. The startup barrier includes a paginated comparison of the complete local canonical manifest with Index's `owner=knowledge` source manifest, so an Index identity missing from a restored backup cannot be silently ignored.

`POST /api/v1/knowledge/sources/verify-revisions` uses the same verification schema as Memory: request `{ "items": [{"source_id":"knowledge:...","revision_sequence":17}], "request_id":"..." }`; response `{ "results": [{"source_id":"knowledge:...","requested_revision_sequence":17,"status":"current|stale|tombstoned|not_found","canonical_revision_sequence":17}], "request_id":"..." }`. It does not return source content and is internal to Gateway's local REST workflow.

## Endpoint status codes

- `POST /api/v1/knowledge/reconciliation/fence`: `200` with `{owner: knowledge, target_generation, fence_id, fence_token, sealed_change_sequence, fence_state: held, expires_at}`; `409 generation_not_caught_up` if the target is not reconciled; `503 cutover_in_progress` for a competing fence or mutation during the active fence. The fence expires within 2 seconds and blocks new canonical commits only. Knowledge registers the fence with Index over REST and invalidates it at Index before resuming writes; if invalidation cannot be confirmed, Knowledge remains fenced until expiry.
- `POST /api/v1/knowledge/reconciliation/fence/release`: `200` when released or already expired; `404 not_found` for an unknown token. Release is idempotent.
- Create/update/delete: `202 Accepted` after the canonical mutation or tombstone is durable; response includes operation identity, canonical mutation status, `indexing_status` (`pending_index`, `indexed`, `index_failed`, or `reconciliation_required`), and `graph_status` for deletion. Delete reaches `status=complete` only when both Index and Graph confirm retrieval-ineligibility. Never wait synchronously for downstream derived representations.
- Direct canonical read and operation status: `200`; unknown ID/operation: `404 not_found`.
- Invalid source/profile shape: `400 invalid_request` or `422 unsupported_profile`; source exceeds profile bounds: `422 source_too_large` before canonical commit.
- Stale expected base sequence, idempotency payload conflict, or sequence allocator regression: `409 revision_conflict`, `409 idempotency_conflict`, or `409 revision_sequence_regression`.
- Owner commit failure before durability: `503 service_unavailable`; request deadline: `504 deadline_exceeded`. A timeout after commit does not undo the mutation.

## Machine-checkable schemas

The normative JSON Schemas for Knowledge requests and responses are in [`schemas/knowledge.schema.json`](schemas/knowledge.schema.json). They define required fields, nullability, bounds, response status shapes, common verification payloads, and cutover fence/release shapes; prose above defines lifecycle invariants.

## Errors and acceptance tests

Use the common error envelope. Distinguish invalid source, invalid scope partition or required local access restriction, revision/idempotency conflict, retention/deletion restriction, dependency unavailable, indexing pending/failed, deadline exceeded, and internal failure. Test immutable revisions, provenance, scope partitioning, deletion/stale-write prevention, REST-only dependencies, partial failure/reconciliation, canonical availability during Index outage, no duplicate retrieval logic, bounded retries, privacy, and restart recovery.

## Approval gate

Review with Memory, Index, Chunking, Tokenization, Embedding, Gateway, source/provenance policy, and end-to-end ingestion/retrieval workflows before implementation.
