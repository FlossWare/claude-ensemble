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
**Pass:** Early cutover is rejected; repeated reconciliation is idempotent; stale/tombstoned content is not published; active writes/deletes are dual-applied to building generations; cutover is fenced and atomic; previous generation is read-only and rollback is explicitly unsupported in v1.

### AT-PERF-01: Nested REST dispatch starvation
Configure dispatcher capacity to 2 concurrent inbound handlers and use gated downstream services to force call depth 3. Start two ingestion requests and gate their bounded Chunking preflight calls; issue health and operation-status requests while both writes are waiting. Release preflight, commit the canonical writes, then keep Tokenization, Embedding, Index, and Graph gates closed.
**Pass:** Health/status requests complete while both preflights are pending, proving nested REST dispatch cannot starve; each preflight is capped at 500 ms; canonical mutations return `202` after preflight and durable commit without waiting for Tokenization, Embedding, Index, or Graph; every synchronous request returns a valid response or stable timeout within its deadline. The hook deadline is 1,500 ms and the interactive default is 5,000 ms. Record per-hop timings, but do not claim these targets are achieved until measured.

### AT-RANK-01: RRF cross-path fusion
Supply lexical and vector result lists with deliberately incompatible raw score scales and 1-based retrieval ranks. Include a candidate returned by both paths, duplicate chunks, and distinct revisions of one source.
**Pass:** `rrf-v1` computes integer `floor(10^12 / (60 + rank))` contributions per unique `list_id`, counts a candidate once per list at its earliest rank, puts exact-identifier matches in a primary tier, preserves distinct revisions, and applies deterministic tie-breaks. Raw BM25 and vector values do not dominate by scale.

### AT-TEXT-01: Unicode span alignment
Process text containing emoji, combining characters, accented text, and non-Latin scripts through Chunking, Tokenization, and Entity Extraction.
**Pass:** All offsets are zero-based, half-open Unicode code-point offsets into the exact original text and slice the same source spans.

### AT-GW-01: Query planning and intent fallback
Submit requests that trigger each initial intent and assert the plan uses only the original query in v1.
**Pass:** Intent labels match the common vocabulary; low-confidence/unknown intent falls back to general with uncertainty; v1 sends exactly one query variant (the original query); all calls share one overall deadline and candidate budget.

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
**Pass:** Every endpoint in the agreed implementation slice has a machine-checkable request/response schema or an explicit cross-cutting schema reference; all 16 service contracts have unique health/readiness routes and explicit ownership. Notion/Git agreement is separately verified manually; this test does not claim it has been verified.

### AT-DELETE-GRAPH-01: Graph projection deletion
Create source-derived graph nodes/edges, update the source revision, and delete the source while delaying a projection retry.
**Pass:** Graph facts carry source identity/revision/sequence; source tombstones make derived facts ineligible; stale projection retries cannot resurrect facts; Memory/Knowledge call Graph over REST and Graph does not call back into owners.

### AT-EMBED-01: Embedding query/document mode
Request embeddings for document and query inputs under a pinned profile.
**Pass:** Results preserve input IDs and explicit input type; incompatible modes/profile combinations fail explicitly; dimensions and finite vector values match the profile.

### AT-TOKEN-BATCH-01: Tokenization batch
Submit up to 64 inputs with unique IDs, then exceed item/body limits and include one invalid item.
**Pass:** Per-item results/errors map to input IDs, order is not used as identity, limits are enforced, and failed items are never silently omitted.

### AT-GEN-02: Concurrent mutation at cutover barrier

Reconcile a target generation through owner watermark W. After the owner reports W, create/update a source and delete another source while cutover is requested. Assert that active mutations are atomically dual-applied or cutover is rejected with `409 generation_not_caught_up`; no acknowledged write is absent from the target and no tombstoned source is eligible.

### AT-GEN-03: Abandon, exclusions, and rollback policy

Abandon a non-active generation and verify it cannot cut over. Attempt to abandon the active generation and verify rejection. Build a target whose profile cannot represent one source. Assert rebuild fails visibly by default, or records a named exclusion only when an explicit exclusion policy was supplied. After cutover, attempt rollback and assert the v1 API rejects it; recovery requires a forward rebuild.

### AT-PROFILE-01: Profile bundle resolution

Resolve an `index_profile` through Index and assert the returned bundle identifies Chunking, Tokenization, lexical policy, Embedding model/mode/dimensions/metric, bounds, and digest. Unknown/retired profile and digest mismatch must be rejected before canonical mutation. Rebuild under a new bundle version must record the exact target profile.

### AT-VERIFY-01: Canonical owner verification

Submit mixed current/stale/tombstoned/not-found candidates and make one owner unavailable. Assert the common verification schema and one result per item. Gateway must fail closed for that owner's candidates, preserve verified candidates from available owners, and never report empty success when all candidates are filtered by verification failure.

### AT-RRF-02: Multiple lists and exact identifier survival

Submit candidates from multiple query-variant/scope/path lists with duplicate candidates within a list, equal mathematical scores, and an exact identifier hit ranked below several non-exact candidates. Assert unique `list_id` accounting, integer fixed-point scores, deterministic ties across runs, and exact-identifier tier precedence. In v1 query expansion is disabled, but multiple scope/path lists remain possible.

### AT-LEARNING-01: Selection and outcome call direction

Call `POST /api/v1/selections` and verify Gateway calls Thompson through REST and returns the selected arm plus state version. Submit `POST /api/v1/outcomes` and verify Gateway calls Learning, Learning validates/persists the event, and Learning calls Thompson through REST exactly once logically under retries. Assert Thompson never calls Learning, duplicate event delivery is idempotent, and status remains queryable after a downstream failure.

### AT-REST-ASYNC-01: Non-blocking ingestion

Gate Tokenization, Embedding, Index, and Graph downstream responses after the bounded Chunking preflight. Create/update must return `202 Accepted` after preflight and canonical commit without waiting for those downstream gates. Dispatcher capacity remains available for health, status, and unrelated reads while preflight handlers are waiting.

### AT-RECOVERY-01: Crash/restart around canonical and derived writes

Crash after canonical commit before Index submission, after Index acceptance before owner status update, mid-generation staging, and during cutover. After restart, retry/reconciliation is idempotent; operation status is truthful; the prior complete revision remains active until atomic publication; tombstones cannot be undone.

### AT-READ-YOUR-WRITES-01: Pending index state

Create a source and immediately issue a recall request while downstream indexing is gated. The write response must return `202 Accepted` with a stable `operation_id` and `indexing_status=pending_index` (or an equivalent explicit pending state). Operation status must distinguish canonical commit from searchable-index completion. When the caller supplies the corresponding `after_operation_id` consistency hint, Gateway must not report a definitive no-result until that operation completes or the deadline produces an explicit degraded result. Ordinary searches without a consistency hint may be eventually consistent, but must not mislabel a known pending operation as fully indexed.

### AT-SEQUENCE-RESTORE-01: Owner sequence allocator regression

Persist source sequence N, accept N into Index, restore an owner backup whose allocator is below N, and attempt a new mutation. Assert the owner rejects the mutation with `409 revision_sequence_regression` until it reconciles the high-water mark; no sequence is reused and Index is not asked to guess ordering.

### AT-ID-01: Source identity and encoded paths

Use source IDs with `/`, `:`, `%`, `?`, and Unicode in the opaque suffix. Assert IDs are encoded as one path segment, decoded once, and routed by the explicit `memory:` or `knowledge:` prefix. Verify endpoints use identical `{source_id, revision_sequence}` payload shapes.

### AT-SCHEMA-02: Contract fixtures and traceability

The six previously prose-only service contracts (Memory, Knowledge, Graph, Thompson, Learning, and Lexical Retrieval), plus Gateway, have linked machine-checkable JSON Schemas for their normative request/response shapes, required fields, types, bounds, nullability, and error envelopes. Validate those schema fixtures and all existing JSON examples against their normative contracts. A traceability matrix maps every functional-inventory row to owner, endpoint/workflow, and acceptance test. Notion/Git agreement is a manual release gate until an automated export/diff is available.

## Traceability gate

The traceability gate is not considered satisfied by prose alone. `docs/TRACEABILITY.md` maps every inventory ID F-01 through F-30 to its owning service/capability, contract endpoint or explicit cross-cutting rule, workflow, and acceptance test. The gate is manual until that matrix is checked into Git and Notion/Git alignment is reviewed.

Before implementation approval, maintain the mapping:
functional requirement → owner/capability → endpoint/contract section → workflow step → acceptance test.

A test name alone is insufficient. Each test must specify fixture/setup, injected failure or concurrent interleaving, observable assertion, and expected error/degraded status. Reviewers should be able to validate fixtures without relying on language-specific implementation details.
