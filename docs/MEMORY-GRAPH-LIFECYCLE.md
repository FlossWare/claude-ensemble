# Memory-to-Graph Projection Lifecycle

Status: implementation plan for the Memory owner integration slice.

## Goals

Memory remains the canonical owner of Memory records. Graph remains a derived relationship index. Memory calls Graph through the internal REST API; Graph never calls Memory directly and never becomes the canonical source of Memory content.

Every accepted create, revision, and deletion must atomically persist its canonical mutation and a durable Graph projection intent in Memory's SQLite database. A projection intent has a stable operation ID, an owner-local monotonically increasing projection sequence, the canonical source revision, and a replayable payload or enough immutable data to reproduce that payload exactly.

## Projection semantics

- A Memory record initially projects a source-supported node with a stable node ID in the `memory:` namespace.
- Updates project the new canonical revision under the same source identity. Graph's source-revision handling replaces that source's prior projection atomically.
- Deletion writes a tombstone intent with a higher canonical revision sequence and a higher owner projection sequence.
- Every Graph REST call uses the durable operation ID as its idempotency identity. A retry must not duplicate graph facts.
- Graph acknowledgements update the corresponding Memory journal row. A failed or unavailable Graph service leaves the operation visibly pending/retryable; Memory must not report full downstream completion.
- Startup recovery replays pending intents in owner-sequence order. It must not skip a failed earlier operation and then claim the owner watermark is complete.
- Concurrent requests must serialize allocation of the owner projection sequence in the same SQLite transaction as the canonical mutation and journal insertion.

## Interactive requests and ingestion

Interactive CE requests remain synchronous request/response. Memory writes acknowledge durable canonical acceptance and expose truthful downstream status. Expensive chunking, tokenization, embedding, Index publication, and Graph projection work run outside the interactive request path.

Background ingestion must not monopolize the HTTP worker pool or shared model/database resources. Concurrency is bounded, and capacity exhaustion is explicit. Small Memory writes are not fire-and-forget: canonical state and durable operation/journal records are committed before returning success.

## Acceptance tests

1. Create and update each produce a durable, ordered Graph intent in the same transaction as the canonical revision.
2. Delete produces a tombstone intent that supersedes prior revisions.
3. Restart after canonical commit but before Graph acknowledgement replays the intent with the same operation ID and sequence.
4. Graph REST failure leaves durable pending status and later recovery completes it without duplicate effects.
5. Concurrent writers allocate unique contiguous owner projection sequences; conflicting reuse fails closed.
6. A stale ingestion cannot overwrite a newer revision or resurrect a tombstoned source.
7. While a deliberately blocked ingestion is running, ordinary health, read, and query-path requests remain serviceable within the configured bounded capacity.
8. Restart during ingestion resumes unfinished work and preserves truthful operation status.
9. Index generation cutover remains fail-closed until owner journals and reconciliation checkpoints are integrated and verified.
