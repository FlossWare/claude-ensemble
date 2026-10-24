# Memory Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Own authoritative memory records and their lifecycle: identity, scope, source revision, metadata, provenance, retention, update/delete semantics, direct lookup, and recovery. Memory records may represent episodic, user, project, or other explicitly defined memory types. The schema and type taxonomy must be reviewed before implementation.

Memory owns its canonical records; Index owns only derived searchable representations. Memory initiates its own ingestion/update/delete workflow and calls Chunking, Tokenization, Embedding, and Index through REST. It must not access those services' storage or call their implementation directly.

## Endpoints

- POST /api/v1/memories: create a memory with an idempotency key.
- GET /api/v1/memories/{memory_id}: direct canonical lookup subject to scope authorization.
- POST /api/v1/memories/{memory_id}/revisions: create a new immutable revision/update.
- DELETE /api/v1/memories/{memory_id}: tombstone/delete the memory under explicit retention and deletion policy.
- GET /api/v1/memories/{memory_id}/operations/{operation_id}: report ingestion/indexing status.
- GET /api/v1/memory/health and GET /api/v1/memory/ready.
- GET /api/v1/memories/reconciliation/manifest: paginated manifest of active canonical revisions and tombstones, with stable snapshot/cursor semantics.
- POST /api/v1/memories/reconciliation: start or resume owner-scoped reconciliation/rebuild into a specified Index generation; return a durable operation ID and status.

The exact CRUD shape may be revised during schema review; revision and operation identity must remain explicit.

## Record and revision semantics

- Each memory has a stable ID, owner/scope, type, created/updated timestamps, retention policy, provenance, and opaque revision IDs paired with a monotonically increasing per-memory revision_sequence.
- Revisions are immutable snapshots. Update creates a new revision rather than mutating content in place; the canonical record identifies the active revision. Revision-update requests supply `expected_base_revision_sequence`; if the active sequence differs, return `409 revision_conflict` rather than silently applying last-write-wins.
- Every write is idempotent. Reusing an idempotency key with a different payload returns conflict.
- Authorization is checked on every create/read/update/delete/status request. Scope is not trusted from caller input alone.
- A delete durably tombstones the canonical record first, allocating a new monotonic `revision_sequence` for the tombstone, and immediately blocks direct reads. It then submits an idempotent Index tombstone carrying that sequence. Report delete complete only after Index confirms durable retrieval-ineligibility; until then report pending/reconciliation-required. While pending, Gateway must verify candidate existence/current revision against Memory before exposing any candidate as current. If verification is unavailable, fail closed for those candidates. Index rejects any upsert at or below the received tombstone sequence; physical cleanup is asynchronous. Tombstone high-water marks survive operation-record expiry and rebuilds.
- Memory is authoritative for whether a record exists and which revision is current. Index status is derived state and may lag; Memory exposes that lag and supports reconciliation.

## Ingestion workflow

1. Validate request, scope, retention, and provenance; durably record the canonical revision and operation identity.
2. Call Chunking over REST with the content and chunker profile/version.
3. Call Tokenization over REST for lexical representations/profile as required.
4. Call Embedding over REST when the active index profile requires vectors.
5. Submit the complete revision representation to Index over REST.
6. Track each stage and expose pending/complete/failed/reconciliation-required state. Do not claim indexing complete until Index confirms publication.

The source write and Index publication are not one distributed transaction. Durable operation state, idempotent retries, and reconciliation are mandatory. Before committing a canonical write, Memory validates that the complete derived representation fits the active Index profile's documented source limits; oversized inputs fail before canonical commit. The canonical memory revision remains readable even if indexing fails, subject to its access policy.

## Owner-led reconciliation and recovery

Memory owns enumeration and replay of its own canonical records; Index must never call back into Memory. The manifest includes active revision IDs/sequences, scope, required profile identity, and tombstone high-water marks. It is paginated against a stable snapshot. Reconciliation stages each current representation and tombstone into the requested Index generation, replays mutations newer than the snapshot, and reports complete only when the owner confirms there is no unreplayed change. Repeated requests are idempotent and restartable. Operators/Gateway initiate Memory and Knowledge reconciliation separately; no new orchestration service is introduced.

## Prompt-time retrieval and injection

Memory supports direct identity lookup and source lifecycle. Generic lexical/vector candidate search is performed by Lexical Retrieval and Vector Retrieval over Index, orchestrated by Gateway; Memory must not duplicate generic search behavior. Gateway/hook integration must support automatic prompt-time memory injection without requiring a manual instruction or special prefix. Returned context includes source identity/revision, scope-safe provenance, and bounded content/evidence.

## Errors and operational rules

Use the common error envelope. Distinguish invalid record, unauthorized scope, idempotency conflict, revision conflict, retention/deletion restriction, dependency unavailable, indexing pending/failed, deadline exceeded, and internal failure. Direct record lookup is distinct from a successful no-match in retrieval. Do not log raw memory content by default.

## Acceptance tests

1. CRUD and revision semantics are idempotent and authorization-enforced.
2. Revision history and active revision are unambiguous after concurrent writes/restarts; concurrent updates with stale `expected_base_revision_sequence` conflict.
3. Delete prevents reads/retrieval under the documented guarantee; delayed upserts are rejected after tombstone receipt and Gateway freshness checks block exposure while tombstone delivery is pending.
4. Each ingestion dependency is called through REST only.
5. Partial ingestion failure is durable, visible, retryable, and reconciled after restart.
6. Memory remains canonical when Index is temporarily unavailable.
7. Generic lexical/vector retrieval is not duplicated in Memory.
8. Automatic prompt-time injection works without manual prompt tricks.
9. Provenance, retention, privacy, deadlines, and bounded retries are enforced.
10. Same-process tests do not claim federation safety.

## Approval gate

Review with Knowledge, Index, Chunking, Tokenization, Embedding, Gateway, scope/retention policy, and end-to-end ingestion/prompt-recall workflows before implementation.
