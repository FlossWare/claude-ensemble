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
  "policy": {"name": "default-fusion", "version": "0.1"},
  "candidates": [{
    "chunk_id": "stable-chunk-id",
    "source_id": "knowledge:project:docs/design.md",
    "source_revision": "rev-17",
    "revision_sequence": 17,
    "retrieval_source": "lexical",
    "retrieval_rank": 1,
    "source_score": 1.234,
    "score_semantics": "bm25",
    "text": "Bounded evidence text",
    "provenance": {"lexical_profile_version": "0.1", "chunker_profile": "markdown-default", "chunker_version": "0.1"}
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
- The default fusion strategy is Reciprocal Rank Fusion (RRF), calculated from each candidate's 1-based `retrieval_rank` within each retrieval source: `rrf_score(candidate) = sum(1 / (k + retrieval_rank))` over sources that returned that candidate. The default `k` is 60 and MUST be part of the named/versioned ranking policy; changing `k` or the formula requires a policy version change. Raw BM25 scores and vector distances/similarities are evidence only and are never directly compared by the default fusion strategy.
- If the same canonical candidate identity appears in multiple retrieval sources, sum its RRF contributions. Deduplicate only by `(source_id, revision_sequence, chunk_id, chunker_profile, chunker_version)`; never merge distinct revisions. Sort by descending RRF score, then deterministic tie-breaks: exact-identifier evidence first when present and declared, then source ID, revision sequence descending, chunk ID, and chunker profile/version lexicographically. Any non-default fusion requires an explicitly named/versioned policy and its own acceptance tests.
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

The default policy `rrf-v1` uses `k = 60` and score `sum(1 / (60 + rank_s))` for each source `s` that returned the candidate; ranks are 1-based and independently assigned by each retrieval source. The policy version identifies the formula, `k`, tie-break rules, and any exact-identifier treatment. Raw source scores and semantics are retained as evidence, not compared across retrieval sources. The response includes RRF score semantics and policy version.

## Approval gate

Review with Lexical Retrieval, Vector Retrieval, Gateway orchestration, Reranking, common candidate identity/provenance, and end-to-end retrieval acceptance tests before implementation.


Candidate identity follows the shared REST rules: source ID, revision sequence, chunk ID, and chunker profile/version. Do not merge evidence from distinct source revisions. Lexical and vector candidate contracts must provide a 1-based `retrieval_rank` so RRF is executable.
