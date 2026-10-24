# Index Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. It defines the shared lifecycle and low-level representation access used by Lexical Retrieval and Vector Retrieval. It does not prescribe a database, index library, or storage engine.

## Responsibility

Index owns derived searchable representations and their lifecycle: revisioned chunk identity, lexical/vector representations, searchable metadata, updates/deletes, operation status, rebuild/reconciliation, and readiness. Memory and Knowledge remain authoritative for source records and revisions. Index must never claim that its derived representation is the authoritative source.

Lexical Retrieval and Vector Retrieval own retrieval policy and evidence semantics. Index provides bounded low-level representation/query operations; it must not absorb query planning, cross-path fusion, or reranking.

## Common rules

- Base path: /api/v1; use the common REST request metadata and error envelope in [REST-CONTRACT.md](REST-CONTRACT.md).
- All operations are scoped by authorized caller and explicit source/project scope.
- Every mutation is idempotent by Idempotency-Key or stable operation ID.
- Every indexed representation records source ID, source revision, chunk ID, chunker profile/version, lexical profile/version, embedding model/version/dimensions where applicable, and operation/index state.
- Older source revisions cannot silently overwrite newer indexed revisions.
- Index operations are bounded; bulk endpoints document item/byte limits.
- Index never calls back into Memory, Knowledge, or retrieval services. Callers initiate workflows, keeping the service graph acyclic.

## Proposed API

### POST /api/v1/index/operations/upsert

Submit a set of representations derived from one source revision. The request is idempotent and may be asynchronous.

Request:

~~~json
{
  "operation_id": "stable-operation-id",
  "source": {
    "source_id": "knowledge:project:docs/design.md",
    "revision": "rev-17",
    "revision_sequence": 17,
    "scope": {
      "project_id": "project-id",
      "visibility": "project"
    }
  },
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
  "source_revision": "rev-17",
  "revision_sequence": 17,
  "delete_scope": "source"
}
~~~

The contract must distinguish deleting one revision from deleting the entire source identity. A delete must not allow an older in-flight upsert to resurrect content.

### GET /api/v1/index/operations/{operation_id}

Return operation status, source identity/revision, accepted/finished timestamps, safe error code when failed, and whether reconciliation is required. Do not return source content.

### GET /api/v1/index/sources/{source_id}/status

Return the latest known source revision, indexed revision, representation profile/model versions, pending operations, deletion state, and readiness/degraded status. Authorize access to the source scope before returning details.

### POST /api/v1/index/lexical/lookup

Provide bounded low-level lexical representation access to Lexical Retrieval. The request supplies already-tokenized terms/profile identity, authorized scope filters, result/candidate limits, and optional source revision constraints. The response returns bounded matching chunk identities, source revisions, matching-term evidence, and the statistics needed by the retrieval strategy. It does not perform cross-retrieval fusion or reranking.

Exact response fields and whether corpus statistics are global, scoped, or per-index remain an explicit contract decision before implementation.

### POST /api/v1/index/vector-neighbors

Provide bounded low-level nearest-neighbor access to Vector Retrieval. The request supplies query vector, model/version/dimensions, metric/profile, authorized scope filters, revision constraints, and candidate limit. The response returns chunk identities, source revisions, and raw distance/similarity values with their declared metric. It does not perform intent-based planning, lexical/vector fusion, or reranking.

The Index service must reject incompatible vector dimensions/model profiles rather than silently comparing them.

## Revision and consistency semantics

- Source ID plus opaque source revision ID and monotonically increasing per-source revision_sequence are the authoritative version key. Never order opaque revision strings lexicographically. chunk_id identifies a deterministic chunk within that revision and chunker profile/version.
- Upsert requests for the same operation ID and identical payload return the same effective outcome. Reusing an idempotency key with a different payload returns conflict.
- Older revision_sequence values cannot replace newer accepted revisions. Out-of-order updates return an explicit superseded/conflict status. Equal sequences are idempotent only for the same revision ID and canonical payload/profile identity; otherwise return conflict.
- Deletion has a defined visibility guarantee. Once the guarantee is reported complete, deleted content must not be returned by retrieval APIs, even if physical cleanup is deferred.
- Index operations can be pending while derived representations are being built. Pending state is visible; it is never reported as fully indexed.
- Representation versions are explicit. Incompatible lexical profiles or vector models/dimensions cannot be silently mixed.
- Source persistence and Index persistence are not one atomic transaction. Memory/Knowledge retain durable operation identity/status and can retry or reconcile after failure. Index supports idempotent repeated operations and status lookup.
- Rebuild/reconciliation is repeatable after restart and does not duplicate or resurrect deleted/stale representations.

## Error behavior

Use the shared error envelope. At minimum distinguish invalid request, unauthorized scope, idempotency conflict, source revision conflict/superseded update, incompatible representation, operation not found, rate/size limit, index unavailable/not ready, and internal failure. A valid empty lookup is not an error; unavailable or incompatible index state is.

## Health and readiness

- GET /api/v1/health: process/liveness only.
- GET /api/v1/ready: whether the service can accept/query representations under its documented readiness policy. Report pending recovery or degraded index state safely.
- Readiness must not imply every source is fully indexed. Per-source status and operation status provide that detail.

## Acceptance tests

1. Repeated upsert with same operation/key is idempotent; conflicting payload under same key returns conflict.
2. Older/out-of-order revisions cannot overwrite newer indexed state.
3. Delete prevents retrieval after the documented visibility guarantee and cannot be undone by an older in-flight upsert.
4. Process failure at each mutation stage can be reconciled after restart.
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
- A request may omit a representation only when the named index profile explicitly permits it. Partial representation updates are not allowed within an already published revision; submit a new source revision or run a controlled rebuild.
- A stable operation ID is required. Reusing it with the same canonical payload returns the existing outcome; reusing it with a different payload returns conflict.

### Revision visibility and stale writes

- Index stages all chunks for a source revision in a non-queryable generation. It validates chunk completeness, profile compatibility, and source-revision ordering before publication.
- Publication is an atomic active-revision switch for that source and scope. Retrieval sees either the previous complete revision or the new complete revision, never a partial mixture.
- A staged revision becomes active only if it is newer than the active revision and not superseded by a tombstone. Equal revisions are idempotent only when their canonical payload/profile identity matches; otherwise return conflict.
- If staging fails, the previous active revision remains queryable. Failed or abandoned staging is visible in operation status and eligible for reconciliation/cleanup.

### Deletion guarantee

- A source-identity delete commits a tombstone that immediately excludes that identity from all retrieval results in the specified scope. The delete operation is reported complete once the tombstone is durably committed, not when physical cleanup finishes.
- A revision-specific delete excludes that revision. It does not delete a newer active revision. The request must state the intended revision and delete scope explicitly.
- Every upsert is checked against revision_sequence and tombstone state at publication. An older or already-tombstoned operation cannot resurrect deleted content. Re-creation requires an explicitly newer source revision after the authoritative owner has re-created the source.
- Physical removal of staged and historical data may be asynchronous. Status distinguishes retrieval-ineligible from physical-cleanup-complete.

### Scope and corpus statistics

- Every operation names an authorization scope and an index profile. Scope authorization is enforced server-side, never trusted from caller-supplied filters alone.
- Lexical corpus statistics are computed within the effective authorized corpus and compatible lexical profile. Statistics must not reveal or let results be influenced by documents outside the caller's authorized scope. If a deployment cannot calculate safe scope-specific statistics, it must use a documented isolated corpus/profile rather than silently share global statistics.
- Index profile identity includes lexical profile/version and, for vector representations, embedding model/version/dimensions plus the configured distance metric. Vector metric is configured per vector profile, not freely selected per request. Incompatible profiles are rejected.

### Rebuild and cutover

- Rebuilds populate a separate generation while the current generation remains queryable.
- A generation is eligible for cutover only after completeness, profile compatibility, revision/tombstone consistency, and configured health checks pass.
- Cutover is an atomic generation-pointer change. Keep the prior generation available for rollback until the new generation passes post-cutover verification and the retention window expires.
- Rebuild and reconciliation are restartable and idempotent. They must not publish stale revisions or resurrect tombstoned sources. Operation/status responses identify the generation used.

### Bounds and synchronous/asynchronous behavior

Initial contract defaults (configuration may lower or raise them only within deployment safety limits):
- Upsert request: maximum 256 chunks and 2 MiB encoded request body.
- Inline completion may be attempted only at or below 16 chunks and 256 KiB; otherwise return 202 Accepted and expose operation status. Inline completion is best-effort within the request deadline, not a guarantee.
- Lexical/vector lookup: default 20 candidates, maximum 100 per call. Larger retrieval plans must use bounded pagination or multiple explicitly bounded calls coordinated by Gateway.
- Responses never include unbounded chunk collections. Source text is returned only where required by the retrieval contract; operation/status endpoints do not return content.
- Deployments must document configured limits and reject excess with the common error envelope. A timeout does not imply failure; callers resolve the outcome using the stable operation ID.

## Approval gate

The decisions above are the proposed baseline for review, not approval to implement. The architecture review may revise them with rationale and updated acceptance tests. No implementation starts until the full service contracts, workflows, ownership, and acceptance criteria are reviewed.
