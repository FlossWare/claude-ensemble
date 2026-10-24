# Ranking Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Fuse, deduplicate, and order a bounded candidate set already gathered by Gateway orchestration. Own ranking policy, feature interpretation, deterministic tie-breaking, and ranking evidence/version metadata. Do not retrieve candidates, query Index, own corpus/source data, or perform second-stage model assessment.

Lexical Retrieval and Vector Retrieval are candidate sources. Gateway chooses which sources to call and supplies their bounded results. Ranking must not call Index, Memory, Knowledge, Lexical Retrieval, or Vector Retrieval directly; this avoids hidden orchestration and keeps the service graph explicit.

## Endpoints

- POST /api/v1/ranking/rank
- GET /api/v1/ranking/health
- GET /api/v1/ranking/ready

## Request

~~~json
{
  "request_id": "correlation-id",
  "policy": {"name": "rrf", "version": "rrf-v1"},
  "candidates": [{
    "chunk_id": "stable-chunk-id",
    "source_id": "knowledge:project:docs/design.md",
    "source_revision": "rev-17",
    "revision_sequence": 17,
    "retrieval_source": "lexical",
    "list_id": "lexical:primary",
    "retrieval_rank": 1,
    "source_score": 1.234,
    "score_semantics": "bm25",
    "text": "Bounded evidence text",
    "chunker": {"profile": "markdown-default", "version": "0.1"},
    "matched_exact_identifiers": ["IDX-17"],
    "provenance": {"lexical_profile_version": "0.1"}
  }],
  "limit": 20
}
~~~

Gateway supplies candidates from the selected scope partition after required local access restrictions and canonical freshness verification. Ranking validates schema and evidence only; it does not make access-control or freshness decisions.

## Response

~~~json
{
  "policy": {"name": "rrf", "version": "rrf-v1"},
  "candidates": [{
    "chunk_id": "stable-chunk-id",
    "source_id": "knowledge:project:docs/design.md",
    "source_revision": "rev-17",
    "revision_sequence": 17,
    "chunker": {"profile": "markdown-default", "version": "0.1"},
    "rank": 1,
    "score": 0.82,
    "score_semantics": "ranking-policy-score",
    "evidence": [{"source": "lexical", "feature": "normalized-rank", "value": 0.9}],
    "provenance": {"lexical_profile_version": "0.1"}
  }],
  "request_id": "correlation-id"
}
~~~

The response score is specific to the named ranking policy/version and is not a universal relevance probability. Explainable evidence is bounded and must not expose sensitive feature values.

## Semantics

- Deduplicate by stable source revision and chunk identity. The exact canonical key must be shared with Gateway and Reranking contracts.
- The normative v1 policy is `{"name":"rrf","version":"rrf-v1"}` with `k=60`. Each retrieval response is a list with a unique `list_id`; candidates carry that `list_id` and a 1-based `retrieval_rank`. For each canonical candidate and each unique list, use only the earliest rank if duplicates occur within that list, then add integer contribution `floor(1_000_000_000_000 / (60 + rank))`. Sum contributions as integers; no floating-point arithmetic participates in ordering. Raw BM25 scores and vector distances/similarities are evidence only and are never compared by scale. Changing formula, scale, k, deduplication, or tie-breaking requires a new policy version.
- Deduplicate only by `(source_id, revision_sequence, chunk_id, chunker.profile, chunker.version)`; never merge distinct revisions. `exact_identifiers` is a required array on the Ranking request (empty is allowed); each candidate may include `matched_exact_identifiers`, but every value MUST exactly equal a member of `exact_identifiers` and be supported by candidate evidence. Exact matching is case-sensitive code-point equality with no normalization. Candidates with at least one exact match sort in a primary tier above every non-exact candidate, then by descending integer RRF score; remaining ties use source ID ascending, revision sequence descending, chunk ID ascending, and chunker profile/version ascending by Unicode code-point order. Any non-default fusion requires an explicitly named/versioned policy and its own acceptance tests.
- Deterministic tie-breaks are required for equivalent inputs and policy version. No hidden network calls or storage access.
- Preserve source identity, revision, chunk identity, and provenance through ranking. Reject or explicitly mark stale/tombstoned candidates according to the shared freshness policy; do not silently invent provenance.
- Bound candidate count, output count, evidence size, and execution time. Propagate correlation ID, deadline, cancellation, and safe errors.
- Do not log raw candidate text by default.

## Errors

Use the common error envelope. Distinguish invalid candidate schema, incompatible/missing evidence, unknown policy/version, candidate limit exceeded, deadline exceeded, and internal failure.

## Acceptance tests

1. Duplicate candidates are deterministically removed using the agreed identity key.
2. RRF is computed from 1-based retrieval ranks using the named policy's `k`; raw lexical/vector score scales do not affect default fusion.
3. Equal candidates produce deterministic order for a fixed policy version.
4. Output includes policy version, rank, score semantics, bounded evidence, and provenance.
5. Invalid/stale evidence is rejected or handled according to an explicit freshness rule.
6. Ranking makes no direct service/storage calls.
7. Limits, deadline, cancellation, and privacy-safe logging are enforced.
8. Same-process tests do not claim federation safety.

### Normative fusion policy

`rrf-v1` uses unique `list_id`, 1-based rank, `k=60`, integer contribution `floor(10^12/(60+rank))`, per-list duplicate collapse to earliest rank, and a primary exact-identifier tier. Output includes policy identity, integer fusion score (as an integer), score semantics `rrf-fixed-1e12`, rank, and bounded evidence.

## Machine-checkable schema and isolated testing

The Ranking request/response JSON Schema is [`schemas/ranking.schema.json`](schemas/ranking.schema.json). Ranking MUST be testable alone with no real retrieval, Index, Memory, or Knowledge services. Use REST-contract fixtures/mocks for input candidates and assert exact integer scores, duplicate-per-list handling, exact-identifier tiering, deterministic tie order, malformed input, limits, deadline, and error envelopes. Ranking must not invoke any outbound service.

## Approval gate

Review with Lexical Retrieval, Vector Retrieval, Gateway orchestration, Reranking, common candidate identity/provenance, and end-to-end retrieval acceptance tests before implementation.


Candidate identity follows the shared REST rules: source ID, revision sequence, chunk ID, and chunker profile/version. Do not merge evidence from distinct source revisions. Lexical and vector candidate contracts must provide a 1-based `retrieval_rank` so RRF is executable.
