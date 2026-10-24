# Index Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. It defines the shared lifecycle and low-level representation access used by Lexical Retrieval and Vector Retrieval. It does not prescribe a database, index library, or storage engine.

## Responsibility

Index owns derived searchable representations and their lifecycle: revisioned chunk identity, lexical/vector representations, searchable metadata, updates/deletes, operation status, rebuild/reconciliation, and readiness. Memory and Knowledge remain authoritative for source records and revisions. Index must never claim that its derived representation is the authoritative source.

Lexical Retrieval and Vector Retrieval own retrieval policy and evidence semantics. Index provides bounded low-level representation/query operations; it must not absorb query planning, cross-path fusion, or reranking.

## Common rules

- Base path: /api/v1; use the common REST request metadata and error envelope in [REST-CONTRACT.md](REST-CONTRACT.md).
- All operations require explicit source/project scope. Any local access restrictions required by the initial deployment are enforced at the owning service; scope is a partition filter, not identity or authorization.
- Every mutating POST requires Idempotency-Key under the common REST contract. operation_id is the stable, queryable operation identity; it may equal the idempotency key but does not silently replace the required header.
- Every indexed representation records source ID, source revision, chunk ID, chunker profile/version, lexical profile/version, embedding model/version/dimensions where applicable, index profile/version, and operation/index state.
- Older source revisions cannot silently overwrite newer indexed revisions. Source-wide tombstone high-water marks are durable and are not removed during physical cleanup.
- Index operations are bounded; bulk endpoints document item/byte limits.
- Index never calls back into Memory, Knowledge, or retrieval services. Callers initiate workflows, keeping the service graph acyclic.

## Profile registry and source identity

Index is the sole owner of the immutable index-profile registry. `GET /api/v1/index/profiles/{name}/{version}` returns the complete profile bundle defined by [`schemas/index-profile.schema.json`](schemas/index-profile.schema.json), including exact Chunking, Tokenization, Lexical and Embedding profile identities, embedding input types/dimensions/normalization/metric, lexical-statistics policy, source/chunk/request limits, status, and SHA-256 digest. A `(name, version)` bundle is immutable; any component/model/limit change requires a new profile version and a rebuild. Memory and Knowledge MUST resolve the bundle through this REST endpoint before accepting a write and MUST NOT infer component profiles from `name` alone. A missing, retired, or digest-mismatched profile fails closed.

Canonical source identity is an opaque owner record ID, not a path or locator. `source_id` grammar is `memory:<base64url-record-id>` or `knowledge:<base64url-record-id>` using unpadded RFC 4648 base64url over the UTF-8 owner record ID; the payload segment contains only `[A-Za-z0-9_-]+`. Knowledge stores `canonical_locator` separately as provenance. In URL paths, percent-encode the complete `source_id` as one path segment (`:` becomes `%3A`); never interpolate raw locators or `/` into a path. Memory/Knowledge verification requests use the identical `{request_id, items:[{source_id, revision_sequence}]}` shape and responses use `{request_id, results:[{source_id, requested_revision_sequence, status, canonical_revision_sequence?}]}` with status `current|stale|tombstoned|not_found`. The owner is routed by the `memory:` / `knowledge:` prefix. A tombstoned identity may be recreated only with an owner-allocated sequence greater than its prior tombstone sequence; source IDs are otherwise never reused.

## Proposed API

### POST /api/v1/index/operations/upsert

Submit a set of representations derived from one source revision. The request is idempotent and may be asynchronous. Omit `target_generation` for normal writes to the active generation. Index MUST durably apply each accepted active-generation upsert/delete/tombstone to every registered building generation as well as the active generation, using one idempotent mutation journal, before reporting the mutation accepted. Owner-led reconciliation may additionally target a generation. Memory and Knowledge retain durable mutation journals and replay every create, update, and tombstone newer than the manifest snapshot before cutover. Each owner mutation carries a monotonically increasing owner-wide `change_cursor`; each generation tracks the highest contiguous cursor applied per owner.

Request:

~~~json
{
  "operation_id": "stable-operation-id",
  "source": {
    "source_id": "knowledge:project:docs/design.md",
    "revision": "rev-17",
    "revision_sequence": 17,
    "scope": {
      "type": "project",
      "id": "project-id",
      "visibility": "private"
    }
  },
  "index_profile": {"name": "default", "version": "0.1"},
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

The vector values above are illustrative only; the supplied vector length must equal the declared dimension. A caller may omit lexical or vector representation only when that representation is not required by the active index profile. Index must validate compatibility rather than silently coerce data.

Response:

~~~json
{
  "operation_id": "stable-operation-id",
  "source_id": "knowledge:project:docs/design.md",
  "source_revision": "rev-17",
  "revision_sequence": 17,
  "status": "accepted",
  "index_generation": "generation-id",
  "request_id": "correlation-id"
}
~~~

Status values: accepted, pending, complete, failed, superseded. The endpoint may return 202 while work is pending. Exact status transitions must be documented and observable.

### POST /api/v1/index/operations/delete

Mark a source revision or source identity as deleted from retrieval eligibility. Physical cleanup may be asynchronous, but the API must define when the deletion guarantee becomes effective.

Request:

~~~json
{
  "operation_id": "stable-delete-operation-id",
  "source_id": "knowledge:project:docs/design.md",
  "source_revision": "tombstone-rev-18",
  "revision_sequence": 18,
  "scope": {"type": "project", "id": "project-id", "visibility": "private"},
  "index_profile": {"name": "default", "version": "0.1"},
  "delete_scope": "source"
}
~~~

V1 supports source-wide deletion only: `delete_scope` MUST be `source`; revision-specific deletion is not supported. `revision_sequence` is the authoritative owner's newly allocated tombstone sequence, strictly greater than every revision previously allocated for that source. Index stores a durable index-wide tombstone high-water mark keyed by canonical `source_id`, outside individual generations, and consults it on every lookup in every generation. It rejects any upsert with `revision_sequence <= tombstone_sequence`, including delayed operations after restart or rebuild. The tombstone survives physical cleanup, generation abandonment, and rebuilds. A tombstoned identity may be recreated only with a new owner-allocated sequence greater than the tombstone sequence.

### POST /api/v1/index/generations

Create an empty, non-queryable target generation for rebuild/reconciliation. Requires `Idempotency-Key` and `index_profile` (`name`, `version`). Response returns `generation_id`, `status` (`building`), effective profile, and `request_id`.

### POST /api/v1/index/generations/{generation_id}/abandon

Abandon a non-active building generation. Requires `Idempotency-Key` and an explicit reason. Active generations cannot be abandoned. Abandonment immediately makes the target ineligible for cutover; staged physical cleanup is asynchronous. Index-wide tombstone high-water marks are never removed.

### GET /api/v1/index/generations/{generation_id}

Return generation status, profile identity, counts, owner-reconciliation checkpoints, validation results, and whether the generation is eligible for cutover.

### POST /api/v1/index/generations/{generation_id}/cutover

Request requires `Idempotency-Key`, the expected active generation ID, and a seal record for each owner (`owner`, `seal_id`, `change_cursor`). Before sealing, the orchestrator asks Memory and Knowledge to seal their change journals; each owner durably fences new canonical mutations until released, returns its final owner-wide cursor, and persists the seal across restart. The owner may queue new writes but MUST NOT acknowledge their canonical commit until the seal is released. Index accepts cutover only when each target generation has applied every owner cursor through both seals, all source entries are either indexed or have an explicit exclusion record, tombstones/profile compatibility pass, and readiness checks succeed. The active-generation pointer change is atomic. If any condition fails, cutover is rejected and the old generation remains active. V1 does not support rollback after cutover; recovery is forward-only. The prior generation is retained read-only for the verification window and then cleaned up.

### GET /api/v1/index/operations/{operation_id}

Return operation status, source identity/revision, accepted/finished timestamps, safe error code when failed, and whether reconciliation is required. Do not return source content.

### GET /api/v1/index/sources/{source_id}/status

Return the latest known source revision and revision_sequence, indexed revision and revision_sequence, representation profile/model versions, pending operations, deletion state, and readiness/degraded status. Apply any local access restrictions required by the deployment before returning details.

### POST /api/v1/index/lexical/lookup

Provide bounded low-level lexical representation access to Lexical Retrieval. The request supplies already-tokenized terms/profile identity, scope partition filters, result/candidate limits, and optional source revision constraints. The response returns bounded matching chunk identities, source revisions, matching-term evidence, and the statistics needed by the retrieval strategy. It does not perform cross-retrieval fusion or reranking.

Corpus statistics are computed only within the scope partition and compatible lexical profile, or within a separately isolated corpus explicitly selected by the profile. Cross-partition statistics must not influence a result or be exposed.

### POST /api/v1/index/vector-neighbors

Provide bounded low-level nearest-neighbor access to Vector Retrieval. The request supplies query vector, model/version/dimensions, metric/profile, scope partition filters, revision constraints, and candidate limit. The response returns chunk identities, source revisions, and raw distance/similarity values with their declared metric. It does not perform intent-based planning, lexical/vector fusion, or reranking.

The Index service must reject incompatible vector dimensions/model profiles rather than silently comparing them.

## Revision and consistency semantics

- Source ID plus opaque source revision ID and monotonically increasing per-source revision_sequence are the authoritative version key. Never order opaque revision strings lexicographically. chunk_id identifies a deterministic chunk within that revision and chunker profile/version.
- Upsert requests for the same operation ID and identical payload return the same effective outcome. Reusing an idempotency key with a different payload returns conflict.
- Index tracks a durable per-source highest-accepted revision sequence separately from the active published sequence. Once sequence N is accepted, any lower sequence remains superseded and may not publish, even if N is still staging or later fails. The prior active complete revision remains queryable until N publishes; recovery retries N or the owner submits a newer sequence. Out-of-order updates return an explicit superseded/conflict status. Equal sequences are idempotent only for the same revision ID and canonical payload/profile identity; otherwise return conflict.
- Deletion has a defined visibility guarantee. Index reports the tombstone operation complete only after the tombstone/high-water mark is durably committed and retrieval-ineligible in the active generation. Because the owner-to-Index REST call can be delayed, Gateway must validate each candidate's source existence and `revision_sequence` against the canonical Memory/Knowledge owner before presenting it as current. A missing/tombstoned source or revision mismatch is filtered; if canonical verification is required but unavailable, Gateway fails closed for those candidates and marks the response degraded/failed rather than treating them as current. This closes the interval before Index receives the tombstone.
- Index operations can be pending while derived representations are being built. Pending state is visible; it is never reported as fully indexed.
- Representation versions are explicit. Incompatible lexical profiles or vector models/dimensions cannot be silently mixed.
- Source persistence and Index persistence are not one atomic transaction. Memory/Knowledge retain durable operation identity/status and can retry or reconcile after failure. Index supports idempotent repeated operations and status lookup.
- Rebuild/reconciliation is repeatable after restart and does not duplicate or resurrect deleted/stale representations.

## Error behavior

Use the shared error envelope. At minimum distinguish invalid request, invalid scope partition, idempotency conflict, source revision conflict/superseded update, incompatible representation, operation not found, rate/size limit, index unavailable/not ready, and internal failure. A valid empty lookup is not an error; unavailable or incompatible index state is.

## Health and readiness

- GET /api/v1/index/health: process/liveness only.
- GET /api/v1/index/ready: whether the service can accept/query representations under its documented readiness policy. Report pending recovery or degraded index state safely.
- Readiness must not imply every source is fully indexed. Per-source status and operation status provide that detail.

## Acceptance tests

1. Repeated upsert with same operation/key is idempotent; conflicting payload under same key returns conflict.
2. Older/out-of-order revisions cannot overwrite newer indexed state.
3. Delete records a durable tombstone high-water mark; stale upserts at or below it are rejected, and Gateway freshness verification prevents exposure during delayed tombstone delivery.
4. Process failure at each mutation stage can be reconciled after restart.
5. Every active mutation reaches all building generations; an interleaved write/delete after the final manifest page but before owner seal is present or tombstoned in the target before cutover.
6. Index-wide tombstone marks are consulted on every generation lookup and survive abandon/rebuild/restart.
7. A profile-version change that makes a source unrepresentable records an explicit exclusion and blocks cutover unless `accept_exclusions=true` is explicitly recorded.
8. A generation can be abandoned safely; v1 rollback after cutover is rejected/not supported.
5. Chunking/tokenization/embedding profile mismatches are explicit and do not silently mix representations.
6. Lexical lookup returns bounded low-level evidence and statistics without owning final ranking/fusion.
7. Vector-neighbor lookup validates model/version/dimensions and reports declared metric semantics.
8. Scope authorization is enforced server-side for update, delete, status, and lookup.
9. Valid no-match is distinguishable from unavailable/not-ready index.
10. Contract tests are language-neutral; single-process tests do not claim federation safety.

## Contract decisions for architecture review

These decisions close the first design pass. They remain proposed until the architecture review accepts or changes them.

### Representation submission

- One idempotent upsert submits all representations and metadata for a single source revision. This keeps the revision as the unit of staging and publication.
- A request may omit a representation only when the resolved profile explicitly permits it. Every stored vector records `input_type: "document"`; query embeddings are never stored as document vectors. Partial representation updates are not allowed within a published revision; submit a new source revision or run a controlled rebuild.
- A stable operation ID is required. Reusing it with the same canonical payload returns the existing outcome; reusing it with a different payload returns conflict.

### Revision visibility and stale writes

- Index stages all chunks for a source revision in a non-queryable generation. It validates chunk completeness, profile compatibility, and source-revision ordering before publication.
- Publication is an atomic active-revision switch for that source and scope. Retrieval sees either the previous complete revision or the new complete revision, never a partial mixture.
- A staged revision becomes active only if it is newer than the active revision and not superseded by a tombstone. Equal revisions are idempotent only when their canonical payload/profile identity matches; otherwise return conflict.
- If staging fails, the previous active revision remains queryable. Failed or abandoned staging is visible in operation status and eligible for reconciliation/cleanup. An unrepresentable source is recorded as an explicit exclusion; a rebuild cannot silently omit it.

### Deletion guarantee

- A source-identity delete commits a tombstone that immediately excludes that identity from all retrieval results in the specified scope. The delete operation is reported complete once the tombstone is durably committed, not when physical cleanup finishes.
- A revision-specific delete excludes that revision. It does not delete a newer active revision. The request must state the intended revision and delete scope explicitly.
- Every upsert is checked against revision_sequence and tombstone state both when accepted and immediately before publication. An older or already-tombstoned operation cannot resurrect deleted content. If an upsert arrives before a delayed tombstone reaches Index, Gateway's mandatory canonical freshness check prevents that representation from being exposed as current; once the tombstone arrives, Index rejects/removes the stale representation. Re-creation requires an explicitly newer source revision after the authoritative owner has re-created the source.
- Physical removal of staged and historical data may be asynchronous. Status distinguishes retrieval-ineligible from physical-cleanup-complete.

### Scope and corpus statistics

- Every operation names an authorization scope and an index profile. Scope filtering is enforced server-side; local access restrictions, where required, are separate from scope semantics.
- Lexical corpus statistics are computed within the effective authorized corpus and compatible lexical profile. Statistics must not reveal or let results be influenced by documents outside the caller's authorized scope. If a deployment cannot calculate safe scope-specific statistics, it must use a documented isolated corpus/profile rather than silently share global statistics.
- Index profile identity includes lexical profile/version and, for vector representations, embedding model/version/dimensions plus the configured distance metric. Vector metric is configured per vector profile, not freely selected per request. Incompatible profiles are rejected.

### Rebuild and cutover

- Index never calls Memory or Knowledge to discover sources. Each canonical owner owns enumeration and reconciliation for its own records, including active revisions and tombstones. Memory and Knowledge expose a paginated, stable reconciliation manifest and an owner-triggered reconciliation operation; operators/Gateway trigger each owner independently. Index accepts idempotent upserts/deletes from those owners into a target generation. A generation cannot cut over until both owners' manifests are reconciled, concurrent changes since manifest creation are replayed, tombstones are applied, and the generation passes completeness/profile checks.
- Rebuilds populate a separate generation while the current generation remains queryable.
- A generation is eligible for cutover only after completeness, profile compatibility, revision/tombstone consistency, owner-seal cursor validation, and configured health checks pass. Every source manifest entry must be either represented or explicitly recorded as `excluded_unrepresentable` with source ID, revision sequence, profile digest, and stable reason code. Exclusions are never silent; cutover requires `accept_exclusions=true` and an explicit operator decision in the operation record, otherwise cutover is rejected.
- Cutover is an atomic generation-pointer change. V1 does not promise rollback after cutover. Keep the prior generation read-only for diagnosis/verification; all post-cutover mutations go only to the active generation and recovery is forward-only.
- Rebuild and reconciliation are restartable and idempotent. They must not publish stale revisions or resurrect tombstoned sources. Operation/status responses identify the generation used.

### Bounds and synchronous/asynchronous behavior

Initial contract defaults (configuration may lower or raise them only within deployment safety limits):
- Upsert request: maximum 256 chunks and 2 MiB encoded request body. Memory/Knowledge must validate the complete derived representation against these limits before accepting a canonical mutation that cannot be indexed under the active profile. Oversized sources are rejected explicitly before canonical commit with `413 request_too_large` or `422 source_too_large`; no partial representation is published. Multipart/staged chunk submission is not part of the initial contract.
- Inline completion may be attempted only at or below 16 chunks and 256 KiB; otherwise return 202 Accepted and expose operation status. Inline completion is best-effort within the request deadline, not a guarantee.
- Lexical/vector lookup: default 20 candidates, maximum 100 per call. Larger retrieval plans must use bounded pagination or multiple explicitly bounded calls coordinated by Gateway.
- Responses never include unbounded chunk collections. Source text is returned only where required by the retrieval contract; operation/status endpoints do not return content.
- Deployments must document configured limits and reject excess with the common error envelope. A timeout does not imply failure; callers resolve the outcome using the stable operation ID.

### Normative lookup schemas

`POST /api/v1/index/lexical/lookup` request fields: `scope` (canonical scope object), `index_profile` (`name`, `version`), `lexical_profile` (`name`, `version`), `terms` (non-empty string array), `limit` (1–100), optional `source_ids` and exact `source_revisions`. Response fields: `candidates` (bounded array of `source_id`, `source_revision`, `revision_sequence`, `chunk_id`, `chunker` profile/version, bounded `text`, matched-term evidence, `retrieval_rank`, and lexical `score` with `score_semantics`), `truncated`, `index_generation`, `request_id`. `corpus_statistics` is calculated only for the effective scope and compatible lexical profile and is returned only when required by the lexical strategy.

`POST /api/v1/index/vector-neighbors` request fields: `scope`, `index_profile`, `embedding_profile` (`name`, `version`, model/version/dimensions), `query_vector`, configured `metric`, and `limit` (1–100), plus optional source filters. Response fields: `candidates` (bounded array of `source_id`, `source_revision`, `revision_sequence`, `chunk_id`, `chunker` profile/version, bounded `text`, `retrieval_rank`, and `distance`/`similarity` with the configured metric/direction), `truncated`, `index_generation`, `request_id`. Both responses preserve the complete candidate identity tuple and never merge different source revisions.

## Approval gate

The decisions above are the proposed baseline for review, not approval to implement. The architecture review may revise them with rationale and updated acceptance tests. No implementation starts until the full service contracts, workflows, ownership, and acceptance criteria are reviewed.
