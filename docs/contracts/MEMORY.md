# Memory Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Own authoritative memory records and their lifecycle: identity, scope, source revision, metadata, provenance, retention, update/delete semantics, direct lookup, and recovery. Memory records may represent episodic, user, project, or other explicitly defined memory types. The schema and type taxonomy must be reviewed before implementation.

Memory owns its canonical records; Index owns only derived searchable representations. Memory initiates its own ingestion/update/delete workflow and calls Chunking, Tokenization, Embedding, and Index through REST. It must not access those services' storage or call their implementation directly.

## Endpoints

- POST /api/v1/memories: create a memory with an idempotency key.
- GET /api/v1/memories/{memory_id}: direct canonical lookup subject to the deployment's required local access restrictions and scope partition filter.
- POST /api/v1/memories/{memory_id}/revisions: create a new immutable revision/update.
- DELETE /api/v1/memories/{memory_id}: tombstone/delete the memory under explicit retention and deletion policy.
- GET /api/v1/memories/{memory_id}/operations/{operation_id} and GET /api/v1/memories/operations/{operation_id}: report canonical commit and indexing status.
- POST /api/v1/memories/revisions/verify: batch-verify candidate source IDs and revision sequences for Gateway freshness checks.
- GET /api/v1/memory/health and GET /api/v1/memory/ready.
- GET /api/v1/memories/reconciliation/manifest: paginated manifest of active canonical revisions and tombstones, with stable snapshot/cursor semantics.
- POST /api/v1/memories/reconciliation: start or resume owner-scoped reconciliation/rebuild into a specified Index generation; return a durable operation ID and status.
- POST /api/v1/memories/reconciliation/fence: acquire a short-lived canonical-write fence for a reconciled target generation.

The exact CRUD shape may be revised during schema review; revision and operation identity must remain explicit.

## Record and revision semantics

- Each memory has a stable ID, owner/scope, type, created/updated timestamps, retention policy, provenance, and opaque revision IDs paired with a monotonically increasing per-memory revision_sequence.
- Revisions are immutable snapshots. Update creates a new revision rather than mutating content in place; the canonical record identifies the active revision. Revision-update requests supply `expected_base_revision_sequence`; if the active sequence differs, return `409 revision_conflict` rather than silently applying last-write-wins.
- Every write is idempotent. Reusing an idempotency key with a different payload returns conflict.
- Any local access restrictions required by the deployment are checked on every create/read/update/delete/status request. Scope is a partition filter and is not trusted as proof of identity.
- A delete durably tombstones the canonical record first, allocating a new monotonic `revision_sequence` for the tombstone, and immediately blocks direct reads. It then submits idempotent Index and Graph source-deletion operations carrying that sequence. Report delete complete only after Index and Graph confirm that all derived representations are retrieval-ineligible; until then report pending/reconciliation-required. While pending, Gateway must verify candidate existence/current revision against Memory before exposing any candidate as current. If verification is unavailable, fail closed for those candidates. Index rejects any upsert at or below the received tombstone sequence; physical cleanup is asynchronous. Tombstone high-water marks survive operation-record expiry and rebuilds.
- Memory is authoritative for whether a record exists and which revision is current. Index status is derived state and may lag; Memory exposes that lag and supports reconciliation.

## Ingestion workflow

1. Validate request, scope, retention, and provenance; durably record the canonical revision and operation identity.
2. Call Chunking over REST with the content and chunker profile/version.
3. Call Tokenization over REST for lexical representations/profile as required.
4. Call Embedding over REST when the active index profile requires vectors.
5. Submit the complete revision representation to Index over REST.
6. If the memory contains explicit relationship facts, submit a source projection to Graph over REST with the same source revision/sequence and provenance.
7. Track Index and Graph stages independently and expose pending/complete/failed/reconciliation-required state. Do not claim the requested derived state complete until required downstream services confirm it. If the complete pipeline cannot finish within the request deadline or inline-completion limits, return `202 Accepted` with the durable operation ID; do not synchronously wait while holding dispatcher capacity needed by downstream REST calls.

The source write and Index publication are not one distributed transaction. Durable operation state, idempotent retries, and reconciliation are mandatory. Before committing a canonical write, Memory validates that the complete derived representation fits the active Index profile's documented source limits; oversized inputs fail before canonical commit. The canonical memory revision remains readable even if indexing fails, subject to its access policy.

## Owner-led reconciliation and recovery

Memory owns enumeration and replay of its own canonical records; Index must never call back into Memory. The manifest includes active revision IDs/sequences, scope, required profile identity, and tombstone high-water marks. It is paginated against a stable snapshot. Reconciliation stages each current representation and tombstone into the requested Index generation, replays mutations newer than the snapshot, and reports complete only when the owner confirms there is no unreplayed change. Repeated requests are idempotent and restartable. Operators/Gateway initiate Memory and Knowledge reconciliation separately; no new orchestration service is introduced.

## Prompt-time retrieval and injection

Memory supports direct identity lookup and source lifecycle. Generic lexical/vector candidate search is performed by Lexical Retrieval and Vector Retrieval over Index, orchestrated by Gateway; Memory must not duplicate generic search behavior. Gateway/hook integration must support automatic prompt-time memory injection without requiring a manual instruction or special prefix. Returned context includes source identity/revision, scope-safe provenance, and bounded content/evidence.

## Normative write schemas

Create `POST /api/v1/memories` requires `Idempotency-Key` and JSON fields `scope`, `type`, `content`, `provenance`, `retention_policy`, and `index_profile`. Before canonical commit, Memory makes one bounded REST preflight call to Chunking to determine the complete chunk count and encoded representation bound under the resolved `index_profile`. The preflight is capped at 500 ms and must not perform Tokenization, Embedding, Index, or Graph work. If preflight times out, no canonical mutation is committed and the endpoint returns `504 deadline_exceeded`; if limits are exceeded, return `422 source_too_large`. After preflight and canonical commit, response is always `202 Accepted` with `operation_id`, `memory_id`, `revision`, `revision_sequence`, `status`, and `indexing_status=pending_index`. No downstream derived work is awaited after canonical commit. A timeout never implies that the mutation did not commit.

Revision update `POST /api/v1/memories/{memory_id}/revisions` requires `Idempotency-Key`, `expected_base_revision_sequence`, new `content`, `provenance`, and effective `index_profile`. A stale base sequence returns `409 revision_conflict`. Response carries `memory_id`, opaque `revision`, new `revision_sequence`, `operation_id`, `status`, and `indexing_status`.

Delete `DELETE /api/v1/memories/{memory_id}` requires a stable idempotency key and explicit delete scope. Response contains `memory_id`, tombstone `revision_sequence`, `operation_id`, and `status` (`pending`, `complete`, or `reconciliation_required`). Canonical reads are blocked as soon as the tombstone commits, even while Index reconciliation is pending.

The freshness endpoint accepts 1–100 `{source_id, revision_sequence}` items and returns one result per input: `current`, `stale`, `tombstoned`, or `not_found`, with the canonical current sequence when safe. It does not return memory content. `source_id` must begin with `memory:`. Gateway routes by that prefix and uses this batch endpoint before exposing candidates.

Reconciliation manifests return `snapshot_id`, a durable `change_cursor`, `next_cursor` (null at end), and bounded `items`. Memory retains a durable mutation journal after that cursor and replays every later create/update/tombstone to the target Index generation until caught up; the final caught-up watermark is returned to Index for cutover validation. Each item includes full `source_id`, active revision/sequence or tombstone sequence, `scope`, and `index_profile`. The owner reconciliation operation requires `Idempotency-Key`, `snapshot_id`, and `target_generation`, and returns `operation_id` and `status`.

## Source identity and verification

Memory source IDs have the grammar `memory:<opaque-owner-id>`, where the suffix is an immutable owner-assigned identifier and may not be parsed by consumers. Owner-local resource paths use `{memory_id}` for the suffix only; service-to-service payloads and verification use the full namespaced `source_id`. Gateway routes by the prefix and removes exactly that prefix before calling a Memory resource path. The owner persists its monotonic sequence allocator independently of operation-record retention. A source ID is never reused for a different logical memory; explicit restoration of the same tombstoned logical memory is permitted only with a revision sequence greater than its tombstone high-water mark. If backup restore would regress the allocator below a sequence already accepted by Index, writes fail with `409 revision_sequence_regression` until the allocator is reconciled; never silently reuse or decrement a sequence. The complete source ID is encoded as a single RFC 3986 path segment when used in a path parameter. Do not construct paths by concatenating unescaped source IDs.

`POST /api/v1/memories/revisions/verify` uses the common verification schema: request `{ "items": [{"source_id":"memory:...","revision_sequence":17}], "request_id":"..." }`; response `{ "results": [{"source_id":"memory:...","requested_revision_sequence":17,"status":"current|stale|tombstoned|not_found","canonical_revision_sequence":17}], "request_id":"..." }`. The `canonical_revision_sequence` field is omitted when it would reveal unavailable or protected data. This endpoint is internal to Gateway's local REST workflow.

## Errors and operational rules

Use the common error envelope. Distinguish invalid record, invalid scope partition or required local access restriction, idempotency conflict, revision conflict, retention/deletion restriction, dependency unavailable, indexing pending/failed, deadline exceeded, and internal failure. Direct record lookup is distinct from a successful no-match in retrieval. Do not log raw memory content by default.

## Endpoint status codes

- `POST /api/v1/memories/reconciliation/fence`: `200` with `{owner: memory, fence_token, sealed_change_cursor, expires_at}`; `409 generation_not_caught_up` if the target is not reconciled; `503 cutover_in_progress` for a competing fence or mutation during the active fence; the fence expires within 2 seconds and blocks new canonical commits only.
- Create/update/delete: `202 Accepted` after the canonical mutation or tombstone is durable; response includes operation identity, canonical mutation status, and `indexing_status` (`pending_index`, `indexed`, `index_failed`, or `reconciliation_required`). Never wait for downstream derived representations.
- Direct canonical read and operation status: `200`; unknown ID/operation: `404 not_found`.
- Invalid record/profile shape: `400 invalid_request` or `422 unsupported_profile`; source exceeds profile bounds: `422 source_too_large` before canonical commit.
- Stale expected base sequence, idempotency payload conflict, or sequence allocator regression: `409 revision_conflict`, `409 idempotency_conflict`, or `409 revision_sequence_regression`.
- Owner commit failure before durability: `503 service_unavailable`; request deadline: `504 deadline_exceeded`. A timeout after commit does not undo the mutation.

## Machine-checkable schemas

The normative JSON Schemas for Memory requests and responses are in [`schemas/memory.schema.json`](schemas/memory.schema.json). They define required fields, nullability, bounds, response status shapes, and common errors; prose above defines lifecycle invariants.

## Acceptance tests

1. CRUD and revision semantics are idempotent and enforce the required local access restrictions and scope partition filters.
2. Revision history and active revision are unambiguous after concurrent writes/restarts; concurrent updates with stale `expected_base_revision_sequence` conflict.
3. Delete prevents reads/retrieval under the documented guarantee; delayed upserts are rejected after tombstone receipt and Gateway freshness checks block exposure while tombstone delivery is pending.
4. Each ingestion dependency is called through REST only.
5. Partial ingestion failure is durable, visible, retryable, and reconciled after restart.
6. Memory remains canonical when Index is temporarily unavailable.
7. Generic lexical/vector retrieval is not duplicated in Memory.
8. Automatic prompt-time injection works without manual prompt tricks.
9. Provenance, retention, privacy, deadlines, and bounded retries are enforced.
10. Same-process tests verify the local REST boundary only; federation is out of scope.

## Approval gate

Review with Knowledge, Index, Chunking, Tokenization, Embedding, Gateway, scope/retention policy, and end-to-end ingestion/prompt-recall workflows before implementation.
