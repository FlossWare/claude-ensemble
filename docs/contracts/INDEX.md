# Index Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. It defines the shared lifecycle and low-level representation access used by Lexical Retrieval and Vector Retrieval. It does not prescribe a database, index library, or storage engine.

## Responsibility

Index owns derived searchable representations and their lifecycle: revisioned chunk identity, lexical/vector representations, searchable metadata, updates/deletes, operation status, rebuild/reconciliation, and readiness. Memory and Knowledge remain authoritative for source records and revisions. Index must never claim that its derived representation is the authoritative source.

Lexical Retrieval and Vector Retrieval own retrieval policy and evidence semantics. Index provides bounded low-level representation/query operations; it must not absorb query planning, cross-path fusion, or reranking.

## Common rules

- Base path: /api/v1; use the common REST request metadata and error envelope in [REST-CONTRACT.md](REST-CONTRACT.md).
- All operations require explicit source/project scope partition. Any local access restrictions required by the initial deployment are enforced at the owning service; scope is a partition filter, not identity.
- Every mutating POST requires Idempotency-Key under the common REST contract. operation_id is the stable, queryable operation identity; it may equal the idempotency key but does not silently replace the required header.
- Every indexed representation records source ID, source revision, chunk ID, chunker profile/version, lexical profile/version, embedding model/version/dimensions and `embedding_input_type=document` where applicable, index profile/version plus bundle digest, and operation/index state.
- Older source revisions cannot silently overwrite newer indexed revisions. Source-wide tombstone high-water marks are durable and are not removed during physical cleanup.
- Index operations are bounded; bulk endpoints document item/byte limits.
- All Index endpoints are internal logical-service APIs reached through the local REST dispatcher; the Gateway is the only client-facing CE API. This is deployment exposure, not an authentication framework. Index never calls back into Memory, Knowledge, or retrieval services. Callers initiate workflows, keeping the service graph acyclic.

## Proposed API

### POST /api/v1/index/operations/upsert

Submit a set of representations derived from one source revision. The request is idempotent and may be asynchronous. Omit `target_generation` for normal writes to the active generation; owner-led rebuild/reconciliation supplies a target generation. Each representation is validated against the target generation's pinned profile. A mutation accepted for active profile P1 does not copy P1 vectors/terms into incompatible target profile P2. Instead, Memory/Knowledge append every canonical change to their durable owner journal and replay that revision through Chunking, Tokenization, Embedding, and Index under P2. The target-generation operation key is `(target_generation, source_id, revision_sequence, index_profile.digest)`; the same source sequence may have distinct derived payloads in distinct profile generations, but within one generation/profile it is idempotent only for the same canonical payload. Index journals accepted target operations and acknowledges the owner change sequence only after its target-generation operation is durable. Cutover requires owner replay through sealed cursors plus Index acknowledgments; no point-in-time owner claim alone is sufficient.

Request:

~~~json
{
  "operation_id": "stable-operation-id",
  "source": {
    "source_id": "knowledge:kn_01J7M6P4V9Q2R8T6W3X5Y0ZABC",
    "revision": "rev-17",
    "revision_sequence": 17,
    "scope": {
      "type": "project",
      "id": "project-id",
      "visibility": "private"
    }
  },
  "index_profile": {"name": "default", "version": "0.1", "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
  "target_generation": "generation-id",
  "representations": [
    {
      "chunk_id": "stable-chunk-id",
      "chunker": {"profile": "markdown-default", "version": "0.1"},
      "text": "# Design",
      "lexical": {
        "profile": "technical-default",
        "version": "0.1",
        "terms": ["design"]
      },
      "vector": {
        "input_type": "document",
        "model": "provider-model-id",
        "version": "model-version",
        "dimensions": 2,
        "values": [0.01, 0.02]
      },
      "metadata": {}
    }
  ]
}
~~~

The vector values above are illustrative only; the supplied vector length must equal the declared dimension. A caller may omit lexical or vector representation only when that representation is not required by the pinned profile. Every representation's canonical serialized size must be at most the profile's `max_chunk_representation_bytes`; the entire upsert must be at most `max_request_bytes`. Index validates compatibility and size rather than silently coercing data.

Response:

~~~json
{
  "operation_id": "stable-operation-id",
  "source_id": "knowledge:kn_01J7M6P4V9Q2R8T6W3X5Y0ZABC",
  "source_revision": "rev-17",
  "revision_sequence": 17,
  "status": "accepted",
  "index_generation": "generation-id",
  "request_id": "correlation-id"
}
~~~

Status values: `accepted`, `pending`, `complete`, `failed`, `superseded`, and `reconciliation_required`. The endpoint returns `202 Accepted` for accepted asynchronous work. `GET /api/v1/index/operations/{operation_id}` reports the same stable status and safe failure code, and includes `replacement_operation_id` when status is `superseded` after re-derivation under a newer profile. A target-generation upsert may complete only when its representation profile digest matches that generation. If a delayed active-generation upsert arrives after cutover with a digest that does not match the active generation, Index MUST reject it with `409 profile_mismatch` and record the operation as `reconciliation_required`; it MUST NOT publish the old-profile payload into the new generation. The owner retains the canonical mutation and durable journal entry, re-derives the same canonical revision under the active profile, and submits a new idempotent Index operation. The original operation remains `reconciliation_required` until the replacement representation is durably accepted, then becomes `superseded` with `replacement_operation_id` in its operation-status response. `GET /api/v1/index/operations/{operation_id}` includes this field only for a superseded operation. This rule applies even when the original operation was accepted by the owner before the cutover but had not reached Index.

### POST /api/v1/index/operations/delete

Mark a source revision or source identity as deleted from retrieval eligibility. Physical cleanup may be asynchronous, but the API must define when the deletion guarantee becomes effective.

Request:

~~~json
{
  "operation_id": "stable-delete-operation-id",
  "source_id": "knowledge:kn_01J7M6P4V9Q2R8T6W3X5Y0ZABC",
  "source_revision": "tombstone-rev-18",
  "revision_sequence": 18,
  "scope": {"type": "project", "id": "project-id", "visibility": "private"},
  "index_profile": {"name": "default", "version": "0.1", "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
  "delete_scope": "source"
}
~~~

V1 supports source-wide deletion only; revision-specific deletion is not part of the initial contract. `delete_scope` MUST be `source`. For `delete_scope: "source"`, `revision_sequence` is the authoritative owner's newly allocated tombstone sequence, strictly greater than every revision previously allocated for that source. Index durably records the source tombstone high-water mark and rejects any upsert with `revision_sequence <= tombstone_sequence`, including delayed operations after restart or rebuild. V1 has no revision-level delete operation; updates create new canonical revisions and deletion is source-wide. The tombstone high-water mark is index-wide, durable, survives generation creation/cutover/retirement and physical cleanup, and is consulted by every lookup before returning a candidate. A source ID is never reassigned to a different logical source. Explicit restoration of the same tombstoned logical source is permitted only with a revision_sequence strictly greater than the tombstone sequence; otherwise its owner allocates a new opaque source ID. Opaque source revision IDs are not ordered.

### GET /api/v1/index/sources/manifest

Accept `owner=memory|knowledge`, a bounded `limit` (1–100), and optional opaque `cursor`. Return a stable paginated snapshot of all Index source identities for that owner, including `latest_revision_sequence`, `indexed_revision_sequence`, and the durable index-wide `tombstone_sequence`; include tombstoned identities, not just live indexed records. The manifest is a diagnostic/reconciliation view, never canonical content. Owners call this endpoint during restore/readiness reconciliation and compare it with their own canonical manifest. Any Index identity missing from the restored owner manifest, or any Index high-water mark above the canonical owner sequence, blocks owner write readiness until explicit operator-directed canonical recovery or a new tombstone resolves it. Index never calls the owner.

### GET /api/v1/index/profiles/{profile_name}/versions/{profile_version}

Resolve an immutable pinned `index_profile` bundle version. Return the complete bundle fields described in Profile bundle resolution, including component profile identities, limits, metric, and SHA-256 digest. Unknown versions return `404 profile_not_found`; retired versions return `409 profile_retired` for new writes but remain readable for existing generation diagnostics.

### POST /api/v1/index/generations

Create an empty, non-queryable target generation for rebuild/reconciliation. Requires `Idempotency-Key` and resolved `index_profile` (`name`, `version`, `digest`) from the Index-owned registry. Response returns `generation_id`, `status` (`building`), effective profile, and `request_id`.

### POST /api/v1/index/generations/{generation_id}/abandon

Requires `Idempotency-Key`. Idempotently mark a non-active building generation abandoned and schedule cleanup. Return `409 active_generation_cannot_be_abandoned` if the ID is active. An abandoned generation cannot be cut over or receive new target-generation upserts.

### GET /api/v1/index/generations/active

Return the active generation's ID, status, immutable `index_profile` identity including digest, and request ID. Gateway calls this once at the start of each retrieval request and pins all lexical/vector lookups and pagination to the returned generation and profile digest. If the active generation cannot be resolved, Gateway does not mix generations or guess a profile; it returns an explicit degraded/failed outcome.

### GET /api/v1/index/generations/{generation_id}

Return generation status, profile identity, counts, owner-reconciliation checkpoints, validation results, applied owner cursors, dual-apply journal position, and whether the generation is eligible for cutover.

### GET /api/v1/index/profiles/{profile_name}/current

Return the registry's current write version for the named profile, including its immutable version, digest, and complete bundle for client/operator discovery. Source mutations MUST still supply an explicit pinned `{name, version, digest}` and owners resolve that exact version through the versioned endpoint; there is no implicit current-profile fallback. A current-pointer change never changes the content digest of an existing version.

### PUT /api/v1/index/generations/{generation_id}/owner-fences/{owner}/{fence_id}

Owners push fence registration to Index over REST after locally acquiring a fence. The body contains `owner`, `target_generation`, `fence_id`, `fence_token`, `sealed_change_sequence`, `expires_at`, and `state=held`. Index accepts registration only when the URL generation/owner/fence identity matches the body, the target generation is building, the expiry is in the future and within the maximum fence TTL, and the owner has acknowledged target replay through `sealed_change_sequence`. Reusing a fence ID with different contents conflicts. Registration replaces no existing held fence.

### DELETE /api/v1/index/generations/{generation_id}/owner-fences/{owner}/{fence_id}

Owner-initiated invalidation. Index atomically marks the registered fence released before the owner resumes canonical writes. If Index cannot confirm invalidation, the owner keeps writes fenced until the token expires; Index rejects expired/released tokens regardless of client-supplied timestamps. Index never calls an owner to validate a fence.

### POST /api/v1/index/generations/{generation_id}/owner-checkpoints

An owner acknowledges a monotonically increasing `applied_change_sequence` only after every journal entry through that sequence has been durably accepted for the target generation under its pinned profile. Index records the owner checkpoint and exposes it from generation status. A checkpoint cannot regress.

### POST /api/v1/index/generations/{generation_id}/cutover

Request requires `Idempotency-Key`, the expected active generation ID, and exactly two `{owner, fence_id, fence_token, sealed_change_sequence}` references, one for `memory` and one for `knowledge`. Index validates these against its registered fence records, including target generation, held state, token, and server-side expiry. Index atomically switches the active-generation pointer only if both fences remain held and unexpired, owner checkpoints equal or exceed the sealed sequences, every owner change through those sequences is represented under the target profile, Index's target journal is drained, tombstones and profile compatibility pass validation, and readiness checks succeed. Fence registration/release is owner-pushed REST; Index does not call source owners. Otherwise return a stable conflict/not-ready error and keep the previous generation active. V1 does not support rollback after cutover. The previous generation is retained read-only for a configured verification window, then may be retired. If post-cutover validation fails, cutover back is not permitted in v1; recovery is a new forward rebuild. This avoids dropping writes or re-exposing tombstoned data.

### GET /api/v1/index/operations/{operation_id}

Return operation status, source identity/revision, accepted/finished timestamps, safe error code when failed, and whether reconciliation is required. Do not return source content.

### GET /api/v1/index/sources/{source_id}/status

Return the latest known source revision and revision_sequence, indexed revision and revision_sequence, representation profile/model versions, pending operations, deletion state, and readiness/degraded status. Apply any local access restrictions required by the deployment before returning details.

### POST /api/v1/index/lexical/lookup

Provide bounded low-level lexical representation access to Lexical Retrieval. The request supplies already-tokenized terms/profile identity, canonical scope partition filters, result/candidate limits, and optional source revision constraints. The response returns bounded matching chunk identities, source revisions, term frequency/document frequency evidence, document lengths, and scope/profile-specific corpus statistics needed by the retrieval strategy. Candidate selection is deterministic: order by descending sum of term frequencies for the requested terms, then `source_id` ascending, `revision_sequence` descending, `chunk_id` ascending, and `chunker.profile` then `chunker.version` ascending. Apply `limit` after this ordering; `truncated=true` means additional eligible candidates were omitted. V1 does not expose pagination or refill. Index does not calculate BM25 or other retrieval-policy scores. Lexical Retrieval owns scoring (including BM25 as a replaceable strategy), candidate ordering, and evidence semantics. Index does not perform cross-retrieval fusion or reranking.

Corpus statistics are computed within the effective profile and scope partition. Lookups are internal service endpoints callable only through the local REST dispatcher by logical callers named by the service call graph; they are not part of the externally exposed Gateway API. This is a deployment exposure rule, not a separate security subsystem.

### POST /api/v1/index/vector-neighbors

Provide bounded low-level nearest-neighbor access to Vector Retrieval. The request supplies query vector, model/version/dimensions, metric/profile, canonical scope partition filters, revision constraints, and candidate limit. The response returns chunk identities, source revisions, and raw distance/similarity values with their declared metric. V1 orders candidates by the metric's natural direction (descending similarity for `cosine` and `dot_product`; ascending distance for `euclidean`), then `source_id` ascending, `revision_sequence` descending, `chunk_id` ascending, `chunker.profile` ascending, and `chunker.version` ascending. These comparators use Unicode code-point order for strings. The returned vector shortlist is deterministic but is not a corpus-wide exact-identifier index. `retrieval_rank` is assigned from this order starting at 1. Index returns at most `limit` results and sets `truncated=true` if more eligible results exist; v1 has no continuation token or pagination. It does not perform intent-based planning, lexical/vector fusion, or reranking.

The Index service must reject incompatible vector dimensions/model profiles rather than silently comparing them. Indexed vectors must have been generated with `input_type=document`; query vectors used by `/vector-neighbors` must be generated with `input_type=query`. The mode is recorded in operation/representation metadata and validated at lookup time. Every lookup consults the index-wide tombstone high-water mark, including when querying a building generation.

## Revision and consistency semantics

- Source ID plus opaque source revision ID and monotonically increasing per-source revision_sequence are the authoritative version key. Never order opaque revision strings lexicographically. chunk_id identifies a deterministic chunk within that revision and chunker profile/version.
- Upsert requests for the same operation ID and identical payload return the same effective outcome. Reusing an idempotency key with a different payload returns conflict.
- Index tracks a durable per-source highest-accepted revision sequence separately from the active published sequence. Once sequence N is accepted, any lower sequence remains superseded and may not publish, even if N is still staging or later fails. The prior active complete revision remains queryable until N publishes; recovery retries N or the owner submits a newer sequence. Out-of-order updates return an explicit superseded/conflict status. Equal sequences are idempotent only for the same revision ID and canonical payload/profile identity; otherwise return conflict.
- Deletion has a defined visibility guarantee. Index reports the tombstone operation complete only after the tombstone/high-water mark is durably committed and retrieval-ineligible in the active generation. Because the owner-to-Index REST call can be delayed, Gateway must validate each candidate's source existence and `revision_sequence` against the canonical Memory/Knowledge owner before presenting it as current. A missing/tombstoned source or revision mismatch is filtered; if canonical verification is required but unavailable, Gateway fails closed for those candidates and marks the response degraded/failed rather than treating them as current. This closes the interval before Index receives the tombstone.
- Index operations can be pending while derived representations are being built. Pending state is visible; it is never reported as fully indexed.
- Representation versions are explicit. Incompatible lexical profiles or vector models/dimensions cannot be silently mixed.
- Source persistence and Index persistence are not one atomic transaction. Memory/Knowledge retain durable operation identity/status and can retry or reconcile after failure. Index supports idempotent repeated operations and status lookup.
- Rebuild/reconciliation is repeatable after restart and does not duplicate or resurrect deleted/stale representations.

## Profile bundle resolution

`index_profile` is a stable bundle identifier, not a free-form label. Index is the authoritative profile registry. Initial bundles are loaded from deployment configuration into Index before readiness; new immutable versions are introduced by an operator-controlled registry update, never by a source mutation. Index exposes `GET /api/v1/index/profiles/{profile_name}/versions/{profile_version}`. Its response envelope is `{name, version, digest, bundle, request_id}`; `bundle` contains the complete profile object defined by [`schemas/index-profile.schema.json`](schemas/index-profile.schema.json). The response includes:

- `name`, `version`, registry lifecycle `status` (`active`, `deprecated`, `retired`). Status is registry metadata and is excluded from the immutable content digest.
- `chunking`: profile name/version and maximum chunk units.
- `tokenization`: profile name/version.
- `lexical`: profile name/version and corpus-statistics policy.
- `embedding`: required flag, model name/version, query/document `input_types`, provider `max_input_tokens`, dimensions, normalization, and distance metric.
- Representation limits: maximum chunks, encoded source bytes, per-chunk text bytes, per-chunk serialized representation bytes, envelope bytes, maximum lexical terms and term bytes, and metadata bytes.
- A canonical content digest over the complete bundle. The digest is SHA-256 over RFC 8785 JSON Canonicalization Scheme output for the bundle with both `digest` and registry lifecycle `status` omitted. A version's component fields and representation limits never change after publication. Index rejects a bundle unless `max_chunks * max_chunk_representation_bytes + max_envelope_bytes <= max_request_bytes` and the per-chunk bound covers worst-case JSON-escaped chunk text, canonical JSON vector (`25 * dimensions + 2` bytes when embeddings are required), configured lexical term count/length, metadata cap, and 1,024 bytes of fixed representation overhead. The profile schema documents the exact formula. Every component enforces these profile bounds against canonical serialized output; Chunking preflight receives the complete resolved bundle and uses the validated per-chunk maximum, not an estimate based only on source text. Preflight guarantees structural/serialized bounds only; Embedding checks actual provider token limits and transient provider failures remain asynchronous operation failures, not reasons to commit partial representations.

Memory and Knowledge resolve the bundle through Index before accepting a source mutation or starting a rebuild. The same immutable bundle digest is carried through Chunking, Tokenization, Embedding, Index upsert, manifests, and generation status. A changed component requires a new `index_profile` version and a rebuild. Unknown, retired, or digest-mismatched bundles are rejected. Index cannot silently choose component profiles.

## Generation lifecycle (v1)

- `POST /api/v1/index/generations` creates a non-queryable generation; `POST /api/v1/index/generations/{id}/abandon` idempotently abandons a non-active generation and schedules cleanup. An active generation cannot be abandoned.
- Every active mutation is journaled by the canonical owner. For a building generation with the same profile digest, Index may dual-apply the accepted representation; for a different profile digest, the owner must re-derive the canonical revision through the target profile and submit a target-generation upsert. In either case, cutover remains blocked until the target generation's owner checkpoints include every mutation through both sealed owner sequences and Index has durably acknowledged all target operations. Failure to derive or apply a mutation records `reconciliation_required` and blocks cutover.
- Owners replay their durable journals from the snapshot sequence into the target. When caught up, each owner acquires a short-lived canonical-write fence bound to the target generation, atomically seals its monotonically increasing change sequence, and pushes the fence registration to Index. The owner acknowledges target replay checkpoints to Index only after all entries through the checkpoint are durable. While fenced, canonical mutations do not commit. Index accepts cutover only when both registered fences remain held/unexpired, both target checkpoints reach the sealed sequences, and the target operation journal is drained. After cutover, release the fences; if cutover fails or tokens expire, release and retry with fresh cursors. This prevents an owner commit from falling between the final watermark and the generation-pointer switch.
- Tombstone high-water marks are index-wide and consulted by active and building-generation lookups. A stale generation cannot make a tombstoned source eligible.
- Rollback is not supported in v1. The previous generation remains read-only during the verification window. Recovery from a bad cutover is a new forward rebuild.
- Sources that cannot fit the target profile are recorded as explicit per-source failures. V1 does not allow exclusion approval: any unrepresentable source blocks generation eligibility and cutover until the source or target profile is corrected. Index never silently skips a source.

## Error behavior

Use the shared error envelope. At minimum distinguish `invalid_request` (400), `not_found`/`profile_not_found` (404), `idempotency_conflict`, `revision_conflict`, `generation_not_caught_up`, and `active_generation_cannot_be_abandoned` (409), `request_too_large` (413), `source_too_large`/`unsupported_profile`/`incompatible_representation` (422), `service_unavailable`/`not_ready` (503), `deadline_exceeded` (504), and `internal_error` (500). A valid empty lookup is not an error; unavailable or incompatible index state is.

## Machine-checkable schemas

The normative Index lifecycle request/response schema is [`schemas/index.schema.json`](schemas/index.schema.json). Its `x-endpoints` map binds every endpoint to request/response definitions, success status, error envelope, and permitted error statuses. It defines upsert/delete, generation creation, cutover fence payloads, source manifest, lookup responses, and lifecycle/error bounds. The profile bundle schema is [`schemas/index-profile.schema.json`](schemas/index-profile.schema.json).

## Health and readiness

- GET /api/v1/index/health: process/liveness only.
- GET /api/v1/index/ready: whether the service can accept/query representations under its documented readiness policy. Report pending recovery or degraded index state safely.
- Readiness must not imply every source is fully indexed. Per-source status and operation status provide that detail.

## Source identity and path encoding

`source_id` is a full namespaced ID: `memory:<opaque-owner-id>` or `knowledge:<opaque-owner-id>`. The owner-assigned suffix MUST match `[A-Za-z0-9._~-]{1,128}`; slash, colon, percent, query/fragment delimiters, whitespace, and non-ASCII characters are invalid in the suffix. Memory and Knowledge assign opaque stable IDs; Knowledge MUST NOT use a canonical locator or file path as its source ID. A deleted ID may be recreated only by its canonical owner with a strictly higher `revision_sequence`; the ID is not reused with its prior sequence. Index accepts the full ID in bodies and query payloads. Any route containing `{source_id}` percent-encodes the entire ID as one RFC 3986 path segment and decodes it exactly once. Consumers may route to Memory or Knowledge using only the prefix; the suffix is opaque.

## Acceptance tests

1. Repeated upsert with same operation/key is idempotent; conflicting payload under same key returns conflict.
2. Older/out-of-order revisions cannot overwrite newer indexed state.
3. Delete records a durable tombstone high-water mark; stale upserts at or below it are rejected, and Gateway freshness verification prevents exposure during delayed tombstone delivery.
4. Process failure at each mutation stage can be reconciled after restart.
5. Chunking/tokenization/embedding profile mismatches are explicit and do not silently mix representations.
6. Lexical lookup returns bounded low-level evidence and statistics without owning final ranking/fusion.
7. Vector-neighbor lookup validates model/version/dimensions and reports declared metric semantics.
8. Scope partition filters are enforced server-side for update, delete, status, and lookup; required local access restrictions are separate.
9. Valid no-match is distinguishable from unavailable/not-ready index.
10. Scope partition isolation tests prove that queries and corpus statistics for one partition cannot return or be influenced by another partition.

## Contract decisions for architecture review

These decisions close the first design pass. They remain proposed until the architecture review accepts or changes them.

### Representation submission

- One idempotent upsert submits all representations and metadata for a single source revision. This keeps the revision as the unit of staging and publication.
- A request may omit a representation only when the named index profile explicitly permits it. Partial representation updates are not allowed within an already published revision; submit a new source revision or run a controlled rebuild.
- A stable operation ID is required. Reusing it with the same canonical payload returns the existing outcome; reusing it with a different payload returns conflict.

### Revision visibility and stale writes

- Index stages all chunks for a source revision in a non-queryable generation. It validates chunk completeness, profile compatibility, and source-revision ordering before publication.
- Publication is an atomic active-revision switch for that source and scope. Retrieval sees either the previous complete revision or the new complete revision, never a partial mixture.
- A staged revision becomes active only if it is newer than the active revision and not superseded by a tombstone. Equal revisions are idempotent only when their canonical payload/profile identity matches; otherwise return conflict.
- If staging fails, the previous active revision remains queryable. Failed or abandoned staging is visible in operation status and eligible for reconciliation/cleanup.

### Deletion guarantee

- An Index source-delete operation is complete once its tombstone is durable and that source identity is retrieval-ineligible in Index; physical cleanup may finish later. This is only the Index stage. Memory/Knowledge must not report their canonical delete operation complete until both Index and Graph independently confirm retrieval-ineligibility, as specified by their owner contracts.
- Revision-specific deletion is unsupported in v1. Updates use a new canonical revision; deletion uses a source-wide tombstone.
- Every upsert is checked against revision_sequence and tombstone state both when accepted and immediately before publication. An older or already-tombstoned operation cannot resurrect deleted content. If an upsert arrives before a delayed tombstone reaches Index, Gateway's mandatory canonical freshness check prevents that representation from being exposed as current; once the tombstone arrives, Index rejects/removes the stale representation. Re-creation requires an explicitly newer source revision after the authoritative owner has re-created the source.
- Physical removal of staged and historical data may be asynchronous. Status distinguishes retrieval-ineligible from physical-cleanup-complete.

### Scope and corpus statistics

- Every operation names a canonical scope partition and an index profile. Scope filtering is enforced server-side; local access restrictions, where required, are separate from scope semantics.
- Lexical corpus statistics are computed within the effective scope partition and compatible lexical profile. Statistics must not reveal or let results be influenced by documents outside the selected scope partition. If a deployment cannot calculate safe scope-specific statistics, it must use a documented isolated corpus/profile rather than silently share global statistics.
- Index profile identity includes lexical profile/version and, for vector representations, embedding model/version/dimensions plus the configured distance metric. Vector metric is configured per vector profile, not freely selected per request. Incompatible profiles are rejected.

### Rebuild and cutover

- Index never calls Memory or Knowledge to discover sources. Each canonical owner owns enumeration and reconciliation for its own records, including active revisions and tombstones. Memory and Knowledge expose a paginated, stable reconciliation manifest and an owner-triggered reconciliation operation; operators/Gateway trigger each owner independently. Index accepts idempotent upserts/deletes from those owners into a target generation. A generation cannot cut over until both owners' manifests are reconciled, concurrent changes since manifest creation are replayed, tombstones are applied, and the generation passes completeness/profile checks.
- Rebuilds populate a separate generation while the current generation remains queryable. Active writes and deletes are dual-applied to all compatible building generations. A target that cannot accept a source because its representation exceeds target profile limits records a structured per-source failure (`source_id`, `revision_sequence`, `reason_code`, profile, retryable flag). In v1, source exclusions cannot be approved: any such failure makes the target generation ineligible for cutover and requires a corrected profile or source before a forward rebuild. Failures are visible in generation status and acceptance reports.
- A generation is eligible for cutover only after completeness, profile compatibility, revision/tombstone consistency, and configured health checks pass. Every active-generation write/delete accepted while a target is building is also applied to that target. Cutover uses a fenced barrier: each owner supplies a durable change watermark; Index verifies that all events through each watermark are applied and that later accepted mutations are dual-applied. If a watermark cannot be verified or a mutation is in flight, cutover returns `409 generation_not_caught_up` and leaves the active pointer unchanged.
- Cutover is an atomic generation-pointer change. Keep the prior generation read-only for a verification window. Rollback is explicitly unsupported in v1; use a forward rebuild to recover from a bad cutover.
- Rebuild and reconciliation are restartable and idempotent. They must not publish stale revisions or resurrect tombstoned sources. Operation/status responses identify the generation used.

### Bounds and synchronous/asynchronous behavior

Initial contract defaults (configuration may lower or raise them only within deployment safety limits):
- Upsert request: maximum 256 chunks and 2 MiB encoded request body. This endpoint explicitly overrides the common 1 MiB request-body default; its hard body limit is 2 MiB. Memory/Knowledge must validate the complete derived representation against these limits before accepting a canonical mutation that cannot be indexed under the active profile. If the encoded Index upsert request body exceeds its explicit 2 MiB limit, return `413 request_too_large`. If a validly encoded source exceeds the active profile's source/chunk/representation limits, return `422 source_too_large`. Memory/Knowledge perform preflight before canonical commit, so no oversized source is committed and no partial representation is published. Multipart/staged chunk submission is not part of the initial contract.
- All Memory/Knowledge ingestion requests return `202 Accepted` after bounded Chunking preflight and durable canonical commit. No request waits for Tokenization, Embedding, Index, or Graph. This avoids nested downstream work consuming dispatcher capacity while the inbound handler remains occupied.
- Lexical/vector lookup: default 20 candidates, maximum 100 per call. V1 does not support pagination or refill. Larger retrieval plans are not issued in v1; callers use one bounded request per retrieval path and propagate `truncated=true` when the result pool is capped. The lexical candidate shortlist is ordered by summed term frequency before Lexical Retrieval applies BM25; this bounded preselection is an explicit v1 quality/cost trade-off and does not guarantee corpus-wide BM25 top-K or exact-identifier recall.
- Responses never include unbounded chunk collections. Source text is returned only where required by the retrieval contract; operation/status endpoints do not return content.
- Deployments must document configured limits and reject excess with the common error envelope. A timeout does not imply failure; callers resolve the outcome using the stable operation ID.

### Normative lookup schemas

`POST /api/v1/index/lexical/lookup` request fields: `scope` (canonical scope object), `index_generation` (the generation pinned by Gateway), `index_profile` (`name`, `version`, `digest`), `lexical_profile` (`name`, `version`), `terms` (non-empty string array), `limit` (1–100), optional `source_ids` and exact `source_revisions`. Response fields: `candidates` (bounded array of `source_id`, `source_revision`, `revision_sequence`, `chunk_id`, `chunker` profile/version, bounded `text`, and term-frequency evidence), `corpus_statistics` (scope/profile-specific N, average document length, and document frequency values for requested terms), `truncated`, `index_generation`, `request_id`. Index returns term-frequency/document-length evidence and corpus statistics only; it does not calculate BM25 scores or assign lexical ranks. `corpus_statistics` is calculated only for the effective scope and compatible lexical profile and is returned only when required by the lexical strategy. Lexical Retrieval owns BM25 scoring and 1-based `retrieval_rank` assignment.

`POST /api/v1/index/vector-neighbors` request fields: `scope`, `index_generation` (the generation pinned by Gateway), `index_profile` (`name`, `version`, `digest`), `embedding_profile` (`name`, `version`, model/version/dimensions), `query_vector`, configured `metric`, and `limit` (1–100), plus optional source filters. Response fields: `candidates` (bounded array of `source_id`, `source_revision`, `revision_sequence`, `chunk_id`, `chunker` profile/version, bounded `text`, `retrieval_rank`, and `distance`/`similarity` with the configured metric/direction), `truncated`, `index_generation`, `request_id`. Both responses preserve the complete candidate identity tuple and never merge different source revisions.

## Approval gate

The decisions above are the proposed baseline for review, not approval to implement. The architecture review may revise them with rationale and updated acceptance tests. No implementation starts until the full service contracts, workflows, ownership, and acceptance criteria are reviewed.
