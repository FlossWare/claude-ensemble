# Vector Retrieval Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Retrieve a bounded candidate set by vector similarity from indexed vector representations. Own vector retrieval behavior, profile compatibility, candidate evidence, and retrieval limits. Call Embedding through REST when query-vector generation is needed and call Index through REST for low-level neighbor lookup. Never access Index storage directly.

This service does not own source records, embeddings as a durable source of truth, index storage, lexical retrieval, cross-path fusion, final ranking, reranking, or Gateway query planning. Vector metrics are configured per compatible vector profile, not chosen arbitrarily by each caller.

## Endpoints

- POST /api/v1/vector-retrieval/search
- GET /api/v1/vector-retrieval/health
- GET /api/v1/vector-retrieval/ready

## Request

~~~json
{
  "query_id": "request-query-id",
  "index_profile": {"name": "default", "version": "0.1", "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
  "scope": {"type": "project", "id": "project-id", "visibility": "private"},
  "embedding_profile": {"name": "technical-default", "version": "0.1", "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
  "query": {"text": "How are revisions published?"},
  "filters": {"source_ids": [], "source_revisions": []},
  "limit": 20,
  "page_token": null
}
~~~

A caller may supply a query vector instead of text only when the vector profile, model/version, dimensions, and query/document mode are explicit and validated. Scope partition filters are enforced server-side; required local access restrictions are separate. Initial maximum is 100 candidates. Requests may include an opaque `page_token`; responses return `next_page_token` when more candidates remain. Pagination is stable for the same query, scope, profile, and Index generation.

## Response

~~~json
{
  "query_id": "request-query-id",
  "index_profile": {"name": "default", "version": "0.1", "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
  "embedding_profile": {"name": "technical-default", "version": "0.1", "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
  "metric": "cosine_distance",
  "candidates": [{
    "chunk_id": "stable-chunk-id",
    "source_id": "knowledge:kn_01J7M6P4V9Q2R8T6W3X5Y0ZABC",
    "source_revision": "rev-17",
    "revision_sequence": 17,
    "chunker": {"profile": "markdown-default", "version": "0.1"},
    "text": "Bounded evidence text for this chunk",
    "retrieval_rank": 1,
    "distance": 0.123,
    "provenance": {"embedding_model_version": "model-revision"}
  }],
  "truncated": false,
  "next_page_token": null,
  "request_id": "correlation-id"
}
~~~

Distance/similarity values must use the declared metric and semantics; lower-is-better or higher-is-better must be explicit. Do not label distance as a normalized relevance score or imply it is comparable to lexical scores.

## Semantics

- Query and indexed vectors must match the configured profile, dimensions, normalization, and compatible query/document modes. Reject mismatches; never pad, truncate, or silently convert vectors.
- Return bounded candidates with source/chunk/revision identity, metric semantics, and provenance. Exclude stale or tombstoned representations.
- Candidate text is bounded and comes from indexed derived representations. If canonical-source freshness verification is required, Gateway orchestrates it through Memory/Knowledge REST APIs.
- Calls to Embedding and Index use REST only. Propagate request ID, deadline, cancellation, and canonical scope partition. Retry transient failures only within remaining deadline; never convert a dependency failure into an empty successful result.
- Valid no-match returns an empty list. Index unavailable/not-ready and profile mismatch are explicit errors. Required local access restrictions are enforced by the owner; scope is a partition filter.
- Do not log raw query text or vectors by default. Log profile/model identifiers, counts, latency, and safe error codes.

## Normative response semantics

Every candidate includes the full shared identity tuple: `source_id`, `revision_sequence`, `chunk_id`, and `chunker` profile/version, plus opaque `source_revision`, bounded `text`, 1-based `retrieval_rank`, metric, and raw distance/similarity semantics. `retrieval_rank` is assigned within the vector result set and consumed by Ranking's RRF policy; raw vector values are never directly compared with lexical scores.

## Errors

Use the common error envelope. Distinguish invalid query, invalid or unavailable local access, unknown/incompatible profile, dimension mismatch, Index unavailable/not ready, Embedding provider failure, invalid limit, deadline exceeded, and internal failure.

## Acceptance tests

1. Profile/model/version/dimension mismatch is rejected.
2. Configured metric and direction semantics are explicit and consistent.
3. Scope enforcement and tombstone/stale-revision exclusion work server-side.
4. Results are bounded and include source/chunk/revision/provenance.
5. No-match differs from dependency failure.
6. Embedding and Index calls are REST-only.
7. Deadline, cancellation, and bounded retries are tested.
8. Raw queries/vectors are not logged by default.
9. Query/document mode compatibility is enforced.

## Approval gate

Review alongside Embedding, Index, Ranking, Gateway orchestration, scope partition filtering, and end-to-end workflows before implementation.


Revision ordering follows the common REST contract: source revision IDs are opaque and must be accompanied by revision_sequence in candidate evidence. Never order opaque revision strings lexicographically. Scope uses the canonical {type, id, visibility} shape.
