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
  "index_generation": "generation-123",
  "index_profile": {"name": "default", "version": "0.1", "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
  "scope": {"type": "project", "id": "project-id", "visibility": "private"},
  "embedding_profile": {"name": "technical-default", "version": "0.1"},
  "query": {"text": "How are revisions published?"},
  "filters": {"source_ids": [], "source_revisions": []},
  "limit": 20
}
~~~

A caller may supply a query vector instead of text only when the vector profile, model/version, dimensions, and query/document mode are explicit and validated. Scope partition filters are enforced server-side; required local access restrictions are separate. Initial maximum is 100 candidates. V1 has no pagination or refill; requests containing `page_token` are invalid and responses never contain `next_page_token`. The caller supplies the pinned `index_generation` and immutable `index_profile` `{name, version, digest}` selected by Gateway. The service rejects a generation/profile mismatch and passes both to Index. The response echoes the same `index_generation` and component profile `{name, version}`. Candidate order is stable for the same query, scope, profile, and pinned Index generation.

## Response

~~~json
{
  "query_id": "request-query-id",
  "index_generation": "generation-123",
  "index_profile": {"name": "default", "version": "0.1", "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
  "embedding_profile": {"name": "technical-default", "version": "0.1"},
  "metric": "cosine",
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
  "request_id": "correlation-id"
}
~~~

Distance/similarity values must use the declared metric and semantics; `cosine` and `dot_product` are higher-is-better similarities; `euclidean` is lower-is-better distance. Direction is part of the immutable Index profile and is never inferred from a numeric score alone. Do not label distance as a normalized relevance score or imply it is comparable to lexical scores.

## Semantics

- Query and indexed vectors must match the configured profile, dimensions, normalization, and compatible query/document modes. Reject mismatches; never pad, truncate, or silently convert vectors.
- Return bounded candidates with source/chunk/revision identity, metric semantics, and provenance. Exclude stale or tombstoned representations.
- Candidate text is bounded and comes from indexed derived representations. If canonical-source freshness verification is required, Gateway orchestrates it through Memory/Knowledge REST APIs.
- Calls to Embedding and Index use REST only. Propagate request ID, deadline, cancellation, and canonical scope partition. Retry transient failures only within remaining deadline; never convert a dependency failure into an empty successful result.
- Valid no-match returns an empty list. Index unavailable/not-ready and profile mismatch are explicit errors. Required local access restrictions are enforced by the owner; scope is a partition filter.
- Do not log raw query text or vectors by default. Log profile/model identifiers, counts, latency, and safe error codes.

## Normative response semantics

The response echoes `index_generation`, `index_profile`, and `embedding_profile` used for the request. Every candidate includes the full shared identity tuple: `source_id`, `revision_sequence`, `chunk_id`, and `chunker` profile/version, plus opaque `source_revision`, bounded `text`, 1-based `retrieval_rank`, metric, and raw distance/similarity semantics. `retrieval_rank` is assigned within the vector result set and consumed by Ranking's RRF policy; raw vector values are never directly compared with lexical scores.

## Machine-checkable schemas

The normative request/response schema is [`schemas/vector-retrieval.schema.json`](schemas/vector-retrieval.schema.json). It defines bounded candidate identity, retrieval ranks, effective embedding profile/model metadata, and the configured distance metric.

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
