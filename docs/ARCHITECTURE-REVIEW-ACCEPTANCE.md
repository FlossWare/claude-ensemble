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
Supply lexical and vector result lists with deliberately incompatible raw score scales and 1-based retrieval ranks. Include a candidate returned by both paths, duplicate chunks, distinct revisions of one source, and two mathematically tied candidates across the two valid v1 lists with rank pairs `(64,98)` and `(98,64)`. Also include duplicate occurrences within a list and an exact identifier hit at the aggregate-pool boundary.
**Pass:** `rrf-v1` computes integer `floor(10^12 / (60 + rank))` contributions per unique `list_id`, counts a candidate once per list at its earliest rank, puts exact-identifier matches in a primary tier, preserves distinct revisions, and applies deterministic tie-breaks. The tied rank pairs produce exactly equal integer totals and the same identity-based order across implementations. Raw BM25 and vector values do not dominate by scale.

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

Create a relationship supported by two sources and a path with two edges, then tombstone one support and later all supports for one edge. Assert the first deletion preserves the relationship through the remaining current support; once an edge has no current support, every path containing it is omitted. Make one support owner unavailable and verify that only independently verified supports can preserve the edge. No stale or unverified support can make a path eligible. Validate Gateway's Graph response fixture against the endpoint schema, including edge direction and each retained support's scope/provenance.

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

Use a controllable clock. Finish owner replay and acquire/register both owner fences for target generation G. In schedule A, request cutover before either fence expires and assert atomic success only when both owner checkpoints and the Index journal cover the sealed cursors. In schedule B, advance the clock beyond one fence expiry before cutover and assert rejection with the active pointer unchanged. Release/invalidate fences and retry the same idempotency keys; each mutation commits exactly once and is indexed in the active generation.

### AT-GEN-03: Abandon, unrepresentable sources, and no rollback

Abandon a non-active generation and verify it cannot cut over. Attempt to abandon the active generation and verify rejection. Build a target whose profile cannot represent one source. Assert it is recorded as a per-source failure, generation status remains failed/ineligible, and cutover is rejected. No exclusion-approval field exists in v1. After cutover, issue `POST /api/v1/index/generations/{previous_generation}/rollback`; assert the route is not defined and returns `404 endpoint_not_found` without changing the active pointer. Recovery requires a forward rebuild.

### AT-PROFILE-01: Profile bundle resolution

Resolve an `index_profile` through Index and assert the returned bundle identifies Chunking, Tokenization, lexical policy, Embedding model/mode/dimensions/metric, bounds, and digest. Unknown/retired profile and digest mismatch must be rejected before canonical mutation. Rebuild under a new bundle version must record the exact target profile.

### AT-PARTIAL-01: One retrieval path unavailable

Return `503` from Vector Retrieval while Lexical Retrieval returns candidates; repeat with both paths unavailable and with Ranking unavailable. Assert one-path success is `status=partial`, degraded, includes a failure entry, and ranks surviving candidates; both retrieval paths unavailable and Ranking unavailable return `status=failed`, never successful empty results. Reranking failure returns the valid Ranking order with a failure entry.

### AT-MAP-01: Source ID owner routing and encoded path

Submit valid `memory:` and `knowledge:` IDs whose suffixes use letters, digits, `.`, `_`, `~`, and `-`. Assert Gateway routes by the exact prefix, sends the full unencoded namespaced ID in the common verification body, and percent-encodes the full ID as one path segment exactly once. Reject suffixes containing `/`, `:`, `%`, `?`, `#`, whitespace, or Unicode at creation and route validation. An unknown or missing prefix fails closed; no locator parsing or fallback owner is allowed.

### AT-FRESH-01: Mass freshness filtering with bounded v1 candidate pools

Return a full bounded candidate pool where canonical verification marks most candidates stale or tombstoned. Keep one retrieval path healthy and the other unavailable; then repeat with both healthy. Assert Gateway performs no pagination/refill in any mode, never broadens scope, and returns only canonically verified candidates. Set `truncated=true` and `status=partial` when a bounded pool or freshness filtering may have omitted relevant results; return `status=failed`, not healthy empty success, when required retrieval/verification failure leaves no safe candidates. In `prompt_recall` mode, the response must remain within 1,500 ms.

### AT-VERIFY-01: Canonical owner verification

Submit mixed current/stale/tombstoned/not-found candidates and make one owner unavailable. Assert the common verification schema and one result per item. Gateway must fail closed for that owner's candidates, preserve verified candidates from available owners, and never report empty success when all candidates are filtered by verification failure.

### AT-HOOK-01: Prompt-hook deadline fail-open

Exhaust the 1,500 ms hook deadline at each reserved stage. Assert the adapter preserves the original prompt, injects no unverified content, emits a safe diagnostic, and never claims that no memory exists.

### AT-RRF-02: Multiple lists and exact identifier survival

Submit candidates from multiple retrieval-path lists with duplicate candidates within a list, equal mathematical scores, and an exact identifier hit ranked below several non-exact candidates. Assert the normative `rl1:{path}:original:{base64url(scope_id)}` list ID, duplicate-list/rank errors, integer fixed-point scores, deterministic ties across runs, and exact-identifier tier precedence. V1 query expansion and public multi-scope requests are disabled.

### AT-OP-ROUTING-01: Owner-qualified operation status

Create Memory and Knowledge operations whose opaque operation suffix is the same string. Assert IDs are `memory:op:<suffix>` and `knowledge:op:<suffix>`, Gateway routes `after_operation_id` only by the exact owner prefix, and no status lookup is sent to the other owner.

### AT-LEARNING-01: Selection and outcome call direction

Call `POST /api/v1/selections` with policy `beta-bernoulli-v1`/`1` and verify an unseen context initializes Beta(1,1) state for each eligible arm. Repeating the same idempotency key returns the same persisted choice; a new key may draw again. Submit success and failure outcomes under `binary-reward-v1` with typed `explicit_user_feedback` evidence and verify Learning maps them to rewards 1 and 0 respectively, then calls Thompson through REST exactly once logically under retries. Submit evidence whose `asserted_result` conflicts with `outcome.result`; assert `400 invalid_request`, no Thompson call, and no state mutation. Assert Thompson never calls Learning, duplicate event delivery is idempotent, and status remains queryable after a downstream failure. Validate Learning operation/state and Thompson state responses against their endpoint-specific schemas, including unknown-operation/context `404` behavior.

### AT-REST-ASYNC-01: Non-blocking ingestion

Gate Tokenization, Embedding, Index, and Graph downstream responses after the bounded Chunking preflight. Create/update must return `202 Accepted` after preflight and canonical commit without waiting for those downstream gates. Dispatcher capacity remains available for health, status, and unrelated reads while preflight handlers are waiting.

### AT-RECOVERY-01: Crash/restart around canonical and derived writes

Run each case as a separate fixture with a durable-state oracle:
1. Owner crashes after canonical commit but before Index submission. The canonical revision and owner journal survive; operation status is pending/reconciliation-required; restart resubmits the same logical operation without duplicating the revision.
2. Index accepts an upsert but the owner crashes before persisting downstream status. After restart, retry with the same idempotency key returns the same Index outcome and the owner reconciles status without a second publication.
3. Index crashes during target-generation staging. The target remains non-queryable; the previous active generation and its complete revision remain queryable; restart resumes or explicitly abandons the target without partial publication.
4. Index crashes during atomic generation cutover or after the pointer switch but before the response is recorded. On restart, exactly one generation is active; retrying the same idempotency key returns the committed result if the switch occurred, otherwise a stable rejection with the old pointer unchanged.
5. Graph crashes after accepting a projection but before the owner checkpoint is recorded. The owner replays the same operation/sequence; Graph applies it idempotently and advances only contiguous watermarks.
6. Graph loses its derived projection store. Memory/Knowledge replay their durable journals through existing Graph projection/deletion REST endpoints without Graph-to-owner calls; Graph stays not-ready until both owner watermarks reach their seals.

For every case, operation status must be truthful, replay must be idempotent, and tombstones must never be undone.

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

### AT-OLD-PROFILE-INFLIGHT-01: Delayed old-profile upsert after cutover

Accept a canonical mutation under active profile P1, hold its P1 Index request, complete a fenced cutover to incompatible profile P2, then release the delayed P1 request. Assert Index rejects it with `409 profile_mismatch`, publishes no P1 representation into P2, and records `reconciliation_required`. The owner re-derives the same canonical revision under P2 with a new operation ID; only after that replacement is durably accepted may the old operation become `superseded` with a replacement-operation reference. Read-your-writes remains `pending_index` or `reconciliation_required` throughout; it must never claim indexed or no-result success.

### AT-INDEX-LEXICAL-ORDER-01: Deterministic bounded Index candidate selection

Submit equal and unequal term-frequency evidence across more than 100 matching chunks, then repeat the same query against the same pinned generation. Assert candidate order is descending sum of requested-term frequencies, then source ID ascending, revision sequence descending, chunk ID ascending, and chunker profile/version ascending. The first 100 are identical across runs, `truncated=true`, and neither Index nor Lexical Retrieval emits a page token in v1.

### AT-PROFILE-CHANGE-01: Concurrent mutation during incompatible-profile rebuild

Keep active generation P1 and build target generation P2 with changed chunking/embedding profile. Commit a source update after target snapshot. Assert the owner journal re-derives that revision under P2, the target operation key includes generation/source/revision/profile digest, and the owner checkpoint advances only after Index durably accepts the P2 representation. Cutover is rejected until every owner checkpoint reaches its sealed sequence and the target journal drains. No P1 vector or lexical representation is copied into P2.

### AT-SIZE-PREFLIGHT-01: Conservative representation-size bound

Resolve a profile whose maximum chunk count times per-chunk representation bound plus envelope bound exceeds the request cap; Index must reject the profile as invalid. For a valid profile, run Chunking preflight on sources just below and above the computed upper bound. Assert the over-bound source is rejected before canonical commit with `422 source_too_large`; a preflight timeout returns `504 deadline_exceeded` without canonical commit. Use control-character-heavy text to exercise worst-case JSON escaping, a maximum-dimension vector, maximum term count/length, and maximum metadata. Assert the profile validator's conservative formula covers each component and that every downstream component rejects any serialized chunk representation larger than the profile cap. A source must never commit and then fail indexing solely because the promised bound was unsound.

### AT-INDEX-DIRECTION-01: No Index-to-owner calls

Instrument the local REST dispatcher with caller-service identity. Run upsert, delete, owner checkpoint, cutover, and recovery flows. Assert the complete trace contains no Index-originated request to Memory or Knowledge; all owner journal replay and fence registration requests are owner-initiated.

### AT-EXACT-RERANK-01: Exact identifier survives reranking and assembly

Supply a verified candidate with exact identifier `REV-17` and a non-exact candidate containing `REV-170`. Assert only the first is exact. Force Reranking to prefer the non-exact candidate and set the final limit to one. Assert Gateway never sends exact-match candidates to Reranking, preserves their identity/evidence and integer RRF score, restores them ahead of reranked non-exact candidates, and context assembly includes the exact identifier whenever a verified exact hit exists and the requested budget can fit its minimal evidence.


### AT-GRAPH-CHECKPOINT-01: Owner-led Graph recovery checkpoint

Erase Graph's derived projection store while retaining the owners' durable Graph journals. Replay Memory and Knowledge Graph events with contiguous `owner_projection_sequence` values, then have each owner submit its sealed sequence to the Graph checkpoint endpoint. Assert Graph remains not-ready while either owner has a gap or applied watermark below its seal; readiness becomes true only when both contiguous applied watermarks reach their sealed sequences. Instrument the dispatcher to prove Graph never calls either owner.


### AT-DEL-RESTART-01: Tombstone delivery gap across restart

Commit a source-wide canonical tombstone while Index and Graph delivery is unavailable, then restart the owner and Index before either derived tombstone is applied. Query through Gateway while the owner is available and the derived stores still contain old representations, then replay the durable owner journal.
**Pass:** Gateway never returns the old revision as current during the gap; the owner reports deletion pending/reconciliation-required until both Index and Graph confirm retrieval-ineligibility; replay is idempotent; index-wide tombstone high-water marks survive generation creation and restart; stale upserts remain rejected.

### AT-GRAPH-IDENTITY-01: Canonical relationship identity and multi-source support

Project the same undirected relationship from two sources using reversed endpoint order and different source-local edge IDs. Repeat with a directed relationship and with a case-different relationship type.
**Pass:** The reversed undirected assertions map to the same canonical `rel:` edge ID with two independently tracked supports; a directed reversal and a case-different relationship type produce distinct identities. Deleting one source removes only its support, leaving the relationship eligible while the other support remains current.

### AT-THOMPSON-STATE-01: Concurrent updates and restart durability

Initialize two arms for one context. Submit two updates with different event IDs and the same `expected_state_version` concurrently; restart Thompson after the committed update, then retry each event with its original idempotency key.
**Pass:** Exactly one update commits against that state version and the other receives `409 revision_conflict`; state version increments once; the committed posterior survives restart; retry does not double-count; selection returns only an eligible arm and same-key retries return the persisted selection without drawing again.

### AT-RESTORE-READY-01: Startup high-water reconciliation

Restore a Memory or Knowledge backup whose canonical revision sequence is lower than Index's durable per-source high-water mark, and remove one canonical record that still exists in the Index manifest. Assert the owner pages `GET /api/v1/index/sources/manifest?owner=...`, reconciles the union of local and Index identities, remains not-ready for writes for both regression and missing canonical content, and reports `revision_sequence_regression` until explicit recovery/tombstone resolution. It must not increment a counter and proceed. Index is never treated as the canonical content source.


### AT-NO-PAGINATION-01: V1 rejects pagination and refill

Submit `page_token` to Vector Retrieval and Graph traversal requests and assert `400 invalid_parameter`. Assert their responses and the Index lexical/vector lookup schemas contain no continuation token. For a truncated candidate pool, Gateway returns the bounded safe results with `truncated=true` and `status=partial` when relevant candidates may be missing; it performs no second retrieval or refill.

### AT-GW-CAP-01: Deterministic aggregate cap and exact-match boundary

Return 100 candidates from each retrieval path, including duplicate identities, exact identifier matches, equal retrieval ranks, and candidates with differing source revisions. Assert Gateway annotates exact matches before capping, retains one unique identity per aggregate-pool slot, orders by exact tier then minimum rank, `list_id`, and canonical identity tuple, and preserves each occurrence's per-list rank/evidence for Ranking. An exact match outside the retrieved/retained pool is not covered by the v1 guarantee; the response is marked truncated/partial.

### AT-GRAPH-RESOLVE-01: Scoped entity mention resolution

Submit entity mentions with exact labels, aliases, substrings, case differences, and Unicode normalization variants. Assert Graph resolves only exact NFC/case-folded label or alias matches within the requested scope, returns at most four node IDs per mention in deterministic order, reports unresolved mentions, and never traverses a node from another scope.

### AT-VECTOR-ORDER-01: Deterministic vector neighbor order

Insert equal-distance and equal-similarity vectors for multiple source revisions/chunks. Assert `cosine` and `dot_product` sort descending, `euclidean` sorts ascending, then the shared canonical identity comparator applies. The same pinned generation produces the same first 100 candidates and truncation flag across runs.

### AT-PREFLIGHT-PROFILE-01: Pinned profile bundle and provider limit boundary

Resolve an immutable profile bundle from Index and pass the full bundle plus matching `{name,version,digest}` to Chunking preflight. Assert a mismatched digest or component identity is rejected before canonical commit; structural and serialized bounds are computed from the supplied bundle. Then inject an Embedding provider outage and a separate input exceeding `max_input_tokens`: the outage is recorded as retryable asynchronous failure, the oversized input fails explicitly without truncation, and neither case publishes a partial Index representation.

### AT-REBUILD-EXCLUSION-01: Unrepresentable source blocks cutover

Build a target generation whose profile cannot represent one canonical source. Assert the owner and Index record a source-specific failure, the target remains ineligible, and cutover is rejected. No caller-supplied exclusion approval is accepted in v1. After correcting the profile/source and replaying the owner journal, the generation may become eligible.

### AT-CALL-GRAPH-01: Static allowed-caller graph

Run `python scripts/check_service_call_graph.py` against all service contract schemas. Assert every endpoint declares a non-empty `x-callers` array, caller names are unique, forbidden Index-to-Memory/Knowledge, Graph-to-Memory/Knowledge, and Thompson-to-Learning edges are rejected, and the service-level caller graph is acyclic. This static check validates declared contracts only; `AT-INDEX-DIRECTION-01` remains the separate runtime dispatcher-trace scenario.
