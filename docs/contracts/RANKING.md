# Ranking Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Fuse, deduplicate, and order a bounded candidate set already gathered by Gateway orchestration. Own ranking policy, feature interpretation, deterministic tie-breaking, and ranking evidence/version metadata. Do not retrieve candidates, query Index, own corpus/source data, or perform second-stage model assessment.

Lexical Retrieval and Vector Retrieval are candidate sources. Gateway chooses which sources to call and supplies their bounded results. Ranking must not call Index, Memory, Knowledge, Lexical Retrieval, or Vector Retrieval directly; this avoids hidden orchestration and keeps the service graph explicit.

## Endpoints

- POST /api/v1/ranking/rank
- GET /api/v1/health
- GET /api/v1/ready

## Request

~~~json
{
  "request_id": "correlation-id",
  "policy": {"name": "default-fusion", "version": "0.1"},
  "candidates": [{
    "chunk_id": "stable-chunk-id",
    "source_id": "knowledge:project:docs/design.md",
    "source_revision": "rev-17",
    "revision_sequence": 17,
    "retrieval_source": "lexical",
    "source_score": 1.234,
    "score_semantics": "bm25",
    "text": "Bounded evidence text",
    "provenance": {"lexical_profile_version": "0.1"}
  }],
  "limit": 20
}
~~~

Gateway supplies only candidates the caller is authorized to see. Ranking must still validate required scope/evidence metadata and reject malformed or incompatible candidate records; it must not treat caller-provided scope as authorization proof.

## Response

~~~json
{
  "policy": {"name": "default-fusion", "version": "0.1"},
  "candidates": [{
    "chunk_id": "stable-chunk-id",
    "source_id": "knowledge:project:docs/design.md",
    "source_revision": "rev-17",
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
- Fusion strategies are replaceable policy implementations, not separate services by default. Strategy choice and version are explicit in output.
- Normalize or transform source scores only under documented strategy semantics. Never assume raw lexical and vector scores share a scale.
- Deterministic tie-breaks are required for equivalent inputs and policy version. No hidden network calls or storage access.
- Preserve source identity, revision, chunk identity, and provenance through ranking. Reject or explicitly mark stale/tombstoned candidates according to the shared freshness policy; do not silently invent provenance.
- Bound candidate count, output count, evidence size, and execution time. Propagate correlation ID, deadline, cancellation, and safe errors.
- Do not log raw candidate text by default.

## Errors

Use the common error envelope. Distinguish invalid candidate schema, incompatible/missing evidence, unknown policy/version, candidate limit exceeded, deadline exceeded, and internal failure.

## Acceptance tests

1. Duplicate candidates are deterministically removed using the agreed identity key.
2. Lexical/vector scores are not treated as directly comparable without an explicit strategy.
3. Equal candidates produce deterministic order for a fixed policy version.
4. Output includes policy version, rank, score semantics, bounded evidence, and provenance.
5. Invalid/stale evidence is rejected or handled according to an explicit freshness rule.
6. Ranking makes no direct service/storage calls.
7. Limits, deadline, cancellation, and privacy-safe logging are enforced.
8. Same-process tests do not claim federation safety.

## Approval gate

Review with Lexical Retrieval, Vector Retrieval, Gateway orchestration, Reranking, common candidate identity/provenance, and end-to-end retrieval acceptance tests before implementation.


Candidate identity follows the shared REST rules: source ID, revision sequence, chunk ID, and chunker profile/version. Do not merge evidence from distinct source revisions.
