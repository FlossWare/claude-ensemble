# Architecture Review Acceptance Test Baseline

Status: normative acceptance criteria for the contract-review corrections. These are implementation-independent scenarios. At least one integration suite must exercise the real single-process REST dispatcher.

## Required tests

### AT-DEL-01: Tombstone versus delayed upsert
1. Create source revision sequence 4 and index it.
2. Commit a canonical source tombstone at sequence 5, but delay delivery of the Index tombstone.
3. Deliver or retry an upsert for sequence 4 while Index has not yet received sequence 5.
4. Query through Gateway before and after tombstone delivery.
**Pass:** Gateway's canonical freshness check never exposes the deleted source as current; when Index receives sequence 5 it durably records the tombstone and rejects/removes any upsert at or below sequence 5. Physical cleanup may finish later. A source delete is not reported complete until Index confirms retrieval-ineligibility.

### AT-REBUILD-01: Owner-led full rebuild and cutover
Create a target Index generation; have Memory and Knowledge enumerate stable paginated manifests containing active revisions and tombstones; mutate/delete sources while reconciliation runs; inject crashes; attempt cutover before and after validation.
**Pass:** Early cutover is rejected; repeated reconciliation is idempotent; stale/tombstoned content is not published; cutover is atomic; previous generation remains available for rollback.

### AT-PERF-01: Nested REST dispatch starvation
Run mixed concurrent ingestion and prompt-recall workloads in the single-process deployment, including downstream delays/failures and saturated inbound concurrency.
**Pass:** No deadlock or unbounded starvation occurs. Every request completes or returns a stable bounded timeout/unavailable result within its deadline. The test does not require all operations to succeed inside one shared 5-second window.

### AT-RANK-01: RRF cross-path fusion
Supply lexical and vector result lists with deliberately incompatible raw score scales and 1-based retrieval ranks. Include a candidate returned by both paths, duplicate chunks, and distinct revisions of one source.
**Pass:** Policy rrf-v1 computes sum(1 / (60 + source_rank)), sums contributions for the same canonical candidate, preserves distinct revisions, and applies deterministic tie-breaks. Raw BM25 and vector values do not dominate by scale.

### AT-TEXT-01: Unicode span alignment
Process text containing emoji, combining characters, accented text, and non-Latin scripts through Chunking, Tokenization, and Entity Extraction.
**Pass:** All offsets are zero-based, half-open Unicode code-point offsets into the exact original text and slice the same source spans.

### AT-GW-01: Query expansion and intent fallback
Submit requests that trigger each initial intent and maximum query expansion.
**Pass:** Intent labels match the common vocabulary; low-confidence/unknown intent falls back to general with uncertainty; no request generates more than three variants including the original; all variants share one overall deadline and candidate budget.

### AT-CONC-01: Concurrent source revisions
Submit two updates based on the same expected base revision sequence.
**Pass:** One update commits; the stale competing update receives 409 revision_conflict; the service never silently overwrites the newer revision.

### AT-IDEMP-01: Lost response and retry
Commit a mutation but drop its response, then retry with the same idempotency key and payload; also retry with a changed payload.
**Pass:** Identical retry returns the original effective operation/result; changed payload returns conflict; pending operations do not expire from the idempotency registry; tombstone high-water marks outlive operation-record retention.

### AT-HEALTH-01: Single-server health route uniqueness
Call the service-qualified health/readiness path for every logical service through the one REST server.
**Pass:** Each path dispatches to exactly one service; no duplicate unqualified health/readiness route collision exists; liveness is distinct from readiness.

### AT-SCHEMA-01: Contract fixtures and traceability
For each endpoint, validate request/response fixtures, required/optional/null semantics, limits, status/error envelopes, idempotency, deadline/cancellation, and provenance. Trace every functional inventory requirement to an owning service/capability, contract section, workflow, and acceptance test.
**Pass:** No endpoint is left with an unspecified request/response schema; all 16 service contracts have unique health/readiness routes and explicit ownership; Notion and Git decisions agree.

### AT-DELETE-GRAPH-01: Graph projection deletion
Create source-derived graph nodes/edges, update the source revision, and delete the source while delaying a projection retry.
**Pass:** Graph facts carry source identity/revision/sequence; source tombstones make derived facts ineligible; stale projection retries cannot resurrect facts; Memory/Knowledge call Graph over REST and Graph does not call back into owners.

### AT-EMBED-01: Embedding query/document mode
Request embeddings for document and query inputs under a pinned profile.
**Pass:** Results preserve input IDs and explicit input type; incompatible modes/profile combinations fail explicitly; dimensions and finite vector values match the profile.

### AT-TOKEN-BATCH-01: Tokenization batch
Submit up to 64 inputs with unique IDs, then exceed item/body limits and include one invalid item.
**Pass:** Per-item results/errors map to input IDs, order is not used as identity, limits are enforced, and failed items are never silently omitted.

## Traceability gate

Before implementation approval, maintain the mapping:
functional requirement → owner/capability → endpoint/contract section → workflow step → acceptance test.

A test name alone is insufficient. Each test must specify fixture/setup, injected failure or concurrent interleaving, observable assertion, and expected error/degraded status. Reviewers should be able to validate fixtures without relying on language-specific implementation details.
