# Architecture Review Acceptance Test Baseline

Status: normative acceptance criteria for the contract-review corrections. These are implementation-independent scenarios. At least one integration suite must exercise the real single-process REST dispatcher.

## Required tests

### AT-DEL-01: Tombstone versus delayed upsert
1. Create source revision sequence 4 and index it.
2. Commit a canonical source tombstone at sequence 5, but delay delivery of the Index tombstone.
3. Deliver or retry an upsert for sequence 4 while Index has not yet received sequence 5.
4. Query through Gateway before and after tombstone delivery.
**Pass:** Gateway's canonical freshness check never exposes the deleted source as current; when Index receives sequence 5 it durably records the tombstone and rejects/removes any upsert at or below sequence 5. Physical cleanup may finish later. Memory/Knowledge must not report the canonical delete complete until both Index and Graph independently confirm that the source is retrieval-ineligible; until then the operation remains pending or reconciliation-required.

### AT-REBUILD-01: Owner-led full rebuild and cutover
Create a target Index generation; have Memory and Knowledge enumerate stable paginated manifests containing active revisions and tombstones; mutate/delete sources while reconciliation runs; inject crashes; attempt cutover before and after validation.
**Pass:** Early cutover is rejected; repeated reconciliation is idempotent; stale/tombstoned content is not published; active writes/deletes are dual-applied to building generations; both owners acquire short-lived canonical-write fences and return sealed cursors; Index accepts cutover only while both fences are valid and all owner/Index journals are drained through those cursors. Mutations arriving during a fence do not commit and receive retryable `503 cutover_in_progress`. Expired fences invalidate cutover. The pointer switch is atomic; prior generation is read-only and rollback is unsupported in v1.

### AT-PERF-01: Nested REST dispatch starvation
Configure two ordinary inbound execution slots, a separately reserved health/status control lane, and gated downstream REST calls at call depth 3. Start two ingestion requests and gate their bounded Chunking preflight calls; issue health and operation-status requests while both writes are waiting. Release preflight, commit the canonical writes, then keep Tokenization, Embedding, Index, and Graph gates closed.
**Pass:** Health/status requests complete through the reserved control lane while both ordinary request slots are awaiting downstream REST, proving nested calls cannot starve liveness/status; each preflight is capped at 500 ms; canonical mutations return `202` after preflight and durable commit without waiting for Tokenization, Embedding, Index, or Graph; every synchronous request returns a valid response or stable timeout within its deadline. The hook deadline is 1,500 ms and the interactive default is 5,000 ms. Record per-hop timings, but do not claim these targets are achieved until measured.

### AT-RANK-01: RRF cross-path fusion
Supply lexical and vector result lists with deliberately incompatible raw score scales and 1-based retrieval ranks. Include a candidate returned by both paths, duplicate chunks, distinct revisions of one source, and two mathematically tied candidates with rank triples `(64,98,58)` and `(98,58,64)`.
**Pass:** `rrf-v1` computes integer `floor(10^12 / (60 + rank))` contributions per unique `list_id`, counts a candidate once per list at its earliest rank, puts exact-identifier matches in a primary tier, preserves distinct revisions, and applies deterministic tie-breaks. The tied rank triples produce exactly equal integer totals and the same identity-based order across implementations. Raw BM25 and vector values do not dominate by scale.

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

### AT-IDEMP-EXPIRY-01: Idempotency expiry under controlled clock

Use a controllable clock. Retry an identical mutation before 30-day retention expiry and assert the original result is returned; advance beyond expiry while retaining the compact expiry marker, then retry the old key. Assert `409 idempotency_key_expired` and no new mutation. Pending/reconciliation-required operations never expire.

### AT-GRAPH-PATH-01: Multi-support and partially stale path

Create a relationship supported by two sources and a path with two edges, then tombstone one support and later all supports for one edge. Assert the first deletion preserves the relationship through the remaining current support; once an edge has no current support, every path containing it is omitted. No stale support can make a path eligible.

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

Reconcile target generation through owner change sequence W. Commit an update/delete before the fence and assert the owner journal replays it into the target. Then acquire/register both generation-bound fences and attempt another update/delete while fenced; assert these mutations do not commit and return `503 cutover_in_progress`. Cutover must not succeed unless owner checkpoints cover all committed changes through the sealed sequences and Index's target journal is drained. No acknowledged write is absent from the target and no tombstoned source is eligible.

### AT-REBUILD-02: Write after owner watermark, before cutover

Replay each owner journal to monotonic change sequence W, acquire target-bound fences, register both with Index, and attempt a create/update and source delete between seal and pointer switch. Assert owner mutations do not commit while fenced; Index validates registered held tokens and expiry, confirms target checkpoints through both sealed sequences, and drains the target operation journal before cutover. Expired, released, mismatched, or unregistered fences reject cutover without changing the active pointer. After successful cutover, retry the same idempotency keys and assert each mutation commits once against the new active profile.

### AT-CUTOVER-SEAL-01: Mutation during final cutover barrier

Finish owner replay, acquire both owner fences, then attempt a write and delete before requesting cutover. Assert those mutations do not commit while fenced; cutover either succeeds before fences expire with all journal positions applied or is rejected after expiry. Release fences and retry the same idempotency keys; each mutation commits exactly once and is indexed in the now-active generation.

### AT-GEN-03: Abandon, exclusions, and rollback policy

Abandon a non-active generation and verify it cannot cut over. Attempt to abandon the active generation and verify rejection. Build a target whose profile cannot represent one source. Assert rebuild fails visibly by default, or records a named exclusion only when an explicit exclusion policy was supplied. After cutover, issue `POST /api/v1/index/generations/{previous_generation}/rollback`; assert the route is not defined and returns `404 endpoint_not_found` without changing the active pointer. Recovery requires a forward rebuild.

### AT-PROFILE-01: Profile bundle resolution

Resolve an `index_profile` through Index and assert the returned bundle identifies Chunking, Tokenization, lexical policy, Embedding model/mode/dimensions/metric, bounds, and digest. Unknown/retired profile and digest mismatch must be rejected before canonical mutation. Rebuild under a new bundle version must record the exact target profile.

### AT-PARTIAL-01: One retrieval path unavailable

Return `503` from Vector Retrieval while Lexical Retrieval returns candidates; repeat with both paths unavailable and with Ranking unavailable. Assert one-path success is `status=partial`, degraded, includes a failure entry, and ranks surviving candidates; both retrieval paths unavailable and Ranking unavailable return `status=failed`, never successful empty results. Reranking failure returns the valid Ranking order with a failure entry.

### AT-MAP-01: Source ID owner routing and encoded path

Submit valid `memory:` and `knowledge:` IDs whose suffixes use letters, digits, `.`, `_`, `~`, and `-`. Assert Gateway routes by the exact prefix, sends the full unencoded namespaced ID in the common verification body, and percent-encodes the full ID as one path segment exactly once. Reject suffixes containing `/`, `:`, `%`, `?`, `#`, whitespace, or Unicode at creation and route validation. An unknown or missing prefix fails closed; no locator parsing or fallback owner is allowed.

### AT-FRESH-01: Mass freshness filtering and bounded refill

Return a full first-page candidate set where canonical verification marks most candidates stale or tombstoned. Keep one retrieval path healthy and the other unavailable; then repeat with both healthy. In `interactive`/`lookup` mode, assert Gateway requests at most one additional bounded page from each successful path that needs refill, re-verifies only new candidates, and never broadens scope. In `prompt_recall` mode, assert no refill occurs and the result returns within 1,500 ms. The response must be partial/degraded when a retrieval path or verification failed; it must not report healthy empty success after candidates are filtered.

### AT-VERIFY-01: Canonical owner verification

Submit mixed current/stale/tombstoned/not-found candidates and make one owner unavailable. Assert the common verification schema and one result per item. Gateway must fail closed for that owner's candidates, preserve verified candidates from available owners, and never report empty success when all candidates are filtered by verification failure.

### AT-HOOK-01: Prompt-hook deadline fail-open

Exhaust the 1,500 ms hook deadline at each reserved stage. Assert the adapter preserves the original prompt, injects no unverified content, emits a safe diagnostic, and never claims that no memory exists.

### AT-RRF-02: Multiple lists and exact identifier survival

Submit candidates from multiple retrieval-path lists with duplicate candidates within a list, equal mathematical scores, and an exact identifier hit ranked below several non-exact candidates. Assert the normative `rl1:{path}:original:{base64url(scope_id)}` list ID, duplicate-list/rank errors, integer fixed-point scores, deterministic ties across runs, and exact-identifier tier precedence. V1 query expansion and public multi-scope requests are disabled.

### AT-OP-ROUTING-01: Owner-qualified operation status

Create Memory and Knowledge operations whose opaque operation suffix is the same string. Assert IDs are `memory:op:<suffix>` and `knowledge:op:<suffix>`, Gateway routes `after_operation_id` only by the exact owner prefix, and no status lookup is sent to the other owner.

### AT-LEARNING-01: Selection and outcome call direction

Call `POST /api/v1/selections` and verify Gateway calls Thompson through REST and returns the selected arm plus state version. Submit `POST /api/v1/outcomes` and verify Gateway calls Learning, Learning validates/persists the event, and Learning calls Thompson through REST exactly once logically under retries. Assert Thompson never calls Learning, duplicate event delivery is idempotent, and status remains queryable after a downstream failure.

### AT-REST-ASYNC-01: Non-blocking ingestion

Gate Tokenization, Embedding, Index, and Graph downstream responses after the bounded Chunking preflight. Create/update must return `202 Accepted` after preflight and canonical commit without waiting for those downstream gates. Dispatcher capacity remains available for health, status, and unrelated reads while preflight handlers are waiting.

### AT-RECOVERY-01: Crash/restart around canonical and derived writes

Crash after canonical commit before Index submission, after Index acceptance before owner status update, mid-generation staging, during cutover, and after Graph loses its derived projection store. After restart, Memory/Knowledge replay their durable journals through Graph's existing projection/deletion endpoints without any Graph-to-owner calls; Graph stays not-ready until owner watermarks are reached. Retry/reconciliation is idempotent; operation status is truthful; the prior complete Index revision remains active until atomic publication; tombstones cannot be undone.

### AT-READ-YOUR-WRITES-01: Pending index state

Create a source and immediately issue a recall request while downstream indexing is gated. The write response must return `202 Accepted` with a stable `operation_id` and `indexing_status=pending_index` (or an equivalent explicit pending state). Operation status must distinguish canonical commit from searchable-index completion. When the caller supplies the corresponding `after_operation_id` consistency hint, Gateway must not report a definitive no-result until that operation completes or the deadline produces an explicit degraded result. Ordinary searches without a consistency hint may be eventually consistent, but must not mislabel a known pending operation as fully indexed.

### AT-SEQUENCE-RESTORE-01: Owner sequence allocator regression

Persist source sequence N, accept N into Index, restore an owner backup whose allocator is below N, and attempt a new mutation. Assert the owner rejects the mutation with `409 revision_sequence_regression` until it reconciles the high-water mark; no sequence is reused and Index is not asked to guess ordering.

### AT-ID-01: Source identity and encoded paths

Use valid source IDs with suffixes containing allowed letters, digits, `.`, `_`, `~`, and `-`; reject suffixes containing `/`, `:`, `%`, `?`, `#`, whitespace, or Unicode. Assert the full valid namespaced ID is percent-encoded as one path segment and decoded once. Verify endpoints use identical `{source_id, revision_sequence}` payload shapes.

### AT-SCHEMA-02: Contract fixtures and traceability

Every service endpoint in the v1 implementation slice has an endpoint-to-request/response schema mapping. Validate all 16 service schema JSON documents plus the Index profile bundle schema, all internal/cross-document references, and every JSON example against its endpoint-specific schema. Include negative fixtures for missing required fields, wrong chunker identity shape, malformed source/operation IDs, duplicate list/ranks, malformed vector dimensions, and stale/released fence tokens. Schema checks are static contract checks; they are not service/runtime tests. A traceability matrix maps every functional-inventory row to owner, endpoint/workflow, and acceptance test. Notion/Git agreement is a manual release gate until an automated export/diff is available.

## Traceability gate

The traceability gate is not considered satisfied by prose alone. `docs/TRACEABILITY.md` maps every inventory ID F-01 through F-30 to its owning service/capability, contract endpoint or explicit cross-cutting rule, workflow, and acceptance test. The gate is manual until that matrix is checked into Git and Notion/Git alignment is reviewed.

Before implementation approval, maintain the mapping:
functional requirement → owner/capability → endpoint/contract section → workflow step → acceptance test.

A test name alone is insufficient. Each test must specify fixture/setup, injected failure or concurrent interleaving, observable assertion, and expected error/degraded status. Reviewers should be able to validate fixtures without relying on language-specific implementation details.


### AT-CUTOVER-FENCE-01: Fence release and stale-token rejection

Acquire and register a Memory fence for generation G, invalidate it through Index, then attempt cutover using the old token before its timestamp expiry. Assert Index rejects the released fence and does not change the active pointer. Repeat with Index unavailable during invalidation: Memory must remain write-fenced until expiry; after expiry, Index rejects the token regardless of the caller's supplied timestamp. Instrument the local dispatcher and assert Index emits no request to Memory or Knowledge.

### AT-PROFILE-CHANGE-01: Concurrent mutation during incompatible-profile rebuild

Keep active generation P1 and build target generation P2 with changed chunking/embedding profile. Commit a source update after target snapshot. Assert the owner journal re-derives that revision under P2, the target operation key includes generation/source/revision/profile digest, and the owner checkpoint advances only after Index durably accepts the P2 representation. Cutover is rejected until every owner checkpoint reaches its sealed sequence and the target journal drains. No P1 vector or lexical representation is copied into P2.

### AT-SIZE-PREFLIGHT-01: Conservative representation-size bound

Resolve a profile whose maximum chunk count times per-chunk representation bound plus envelope bound exceeds the request cap; Index must reject the profile as invalid. For a valid profile, run Chunking preflight on sources just below and above the computed upper bound. Assert the over-bound source is rejected before canonical commit with `422 source_too_large`; a preflight timeout returns `504 deadline_exceeded` without canonical commit. Verify every downstream component rejects any serialized chunk representation larger than the profile cap. A source must never commit and then fail indexing solely because the promised bound was unsound.

### AT-INDEX-DIRECTION-01: No Index-to-owner calls

Instrument the local REST dispatcher with caller-service identity. Run upsert, delete, owner checkpoint, cutover, and recovery flows. Assert the complete trace contains no Index-originated request to Memory or Knowledge; all owner journal replay and fence registration requests are owner-initiated.

### AT-EXACT-RERANK-01: Exact identifier survives reranking and assembly

Supply a verified candidate with exact identifier `REV-17` and a non-exact candidate containing `REV-170`. Assert only the first is exact. Force Reranking to prefer the non-exact candidate and set the final limit to one. Assert Reranking preserves exact-match candidates and evidence, Gateway restores the exact tier after Reranking, and context assembly includes the exact identifier whenever a verified exact hit exists and the requested budget can fit its minimal evidence.


### AT-RESTORE-READY-01: Startup high-water reconciliation

Restore a Memory or Knowledge backup whose canonical revision sequence is lower than Index's durable per-source high-water mark. Assert the owner remains not-ready for writes, reports `revision_sequence_regression`, and does not increment a counter and proceed. A source whose canonical content is missing requires explicit canonical recovery or a new tombstone; Index is never treated as the canonical content source.
