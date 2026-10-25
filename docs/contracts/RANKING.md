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
  "policy": {"name": "rrf-v1", "version": "1"},
  "exact_identifiers": ["REV-17"],
  "lists": [{
    "list_id": "rl1:lexical:original:cHJvamVjdC1pZA",
    "retrieval_path": "lexical",
    "query_variant_id": "original",
    "scope_partition_id": "project-id",
    "candidates": [{
    "chunk_id": "stable-chunk-id",
    "source_id": "knowledge:kn_01J7M6P4V9Q2R8T6W3X5Y0ZABC",
    "source_revision": "rev-17",
    "revision_sequence": 17,
    "retrieval_source": "lexical",
    "retrieval_rank": 1,
    "matched_exact_identifiers": ["REV-17"],
    "source_score": 1.234,
    "score_semantics": "bm25",
    "text": "Bounded evidence text",
    "chunker": {"profile": "markdown-default", "version": "0.1"},
    "provenance": {"lexical_profile": "technical-default", "lexical_profile_version": "0.1"}
    }]
  }],
  "limit": 20
}
~~~

Gateway supplies only candidates allowed by the selected scope partition and any required local access restrictions. Ranking validates scope/evidence metadata and rejects malformed or incompatible candidate records; it does not make access-control decisions.

## Response

~~~json
{
  "policy": {"name": "rrf-v1", "version": "1"},
  "score_scale": 1000000000000,
  "candidates": [{
    "chunk_id": "stable-chunk-id",
    "source_id": "knowledge:kn_01J7M6P4V9Q2R8T6W3X5Y0ZABC",
    "source_revision": "rev-17",
    "revision_sequence": 17,
    "chunker": {"profile": "markdown-default", "version": "0.1"},
    "text": "Bounded evidence text",
    "rank": 1,
    "score": 16393442622,
    "score_semantics": "rrf-v1-fixed-point-1e12",
    "matched_exact_identifiers": ["REV-17"],
    "evidence": [{"source": "lexical", "feature": "normalized-rank", "value": 0.9}],
    "provenance": {"lexical_profile_version": "0.1"}
  }],
  "request_id": "correlation-id"
}
~~~

The response score is specific to the named ranking policy/version and is not a universal relevance probability. Explainable evidence is bounded and must not expose sensitive feature values.

## Semantics

- Deduplicate by stable source revision and chunk identity. The exact canonical key must be shared with Gateway and Reranking contracts.
- The default fusion strategy is `rrf-v1`. Each ranked list has a unique normative `list_id` in v1: `rl1:{retrieval_path}:original:{scope_partition_id_base64url}`, where the final segment is unpadded base64url of UTF-8 scope partition ID. `query_variant_id` is exactly `original` in v1. Duplicate `list_id` returns `400 duplicate_list_id`; duplicate `retrieval_rank` values within one list return `400 duplicate_retrieval_rank`. Each candidate contributes at most once per `list_id`, using its earliest 1-based rank in that list. For each list contribution calculate the integer `floor(10^12 / (60 + rank))`; sum these integers across distinct lists. This fixed-point rule avoids floating-point implementation differences. The scale and `k=60` are normative; changes require a new policy version. Raw BM25 scores and vector distances/similarities are evidence only and are never directly compared.
- Deduplicate only by `(source_id, revision_sequence, chunk_id, chunker.profile, chunker.version)`; never merge distinct revisions. The Ranking request has an optional `exact_identifiers` array (maximum 32, each 1–256 Unicode code points). A candidate carries `matched_exact_identifiers`, which must be a subset of that request array. Gateway sets a match only when the extracted identifier equals a complete identifier span in evidence or structured metadata after Unicode NFC normalization and case folding; substring matches are invalid (`REV-17` does not match `REV-170`). Candidates matching at least one requested exact identifier form a primary tier ahead of all non-exact candidates; RRF orders candidates within each tier. This is a v1 correctness guarantee, not merely a tie-break. Within a tier, sort by descending integer RRF score, then `source_id` ascending, `revision_sequence` descending, `chunk_id` ascending, and chunker profile/version ascending by Unicode code-point order. Any non-default fusion requires an explicitly named/versioned policy and its own acceptance tests.
- Deterministic tie-breaks are required for equivalent inputs and policy version. No hidden network calls or storage access.
- Preserve source identity, revision, chunk identity, and provenance through ranking. Ranking does not call canonical owners and does not verify freshness; Gateway owns canonical freshness verification before Ranking. Reject malformed identity/provenance fields, but preserve candidates' freshness metadata without independently reclassifying it.
- Bound candidate count, output count, evidence size, and execution time. Propagate correlation ID, deadline, cancellation, and safe errors.
- Do not log raw candidate text by default.

## Machine-checkable schemas

The normative Ranking request/response JSON Schema is [`schemas/ranking.schema.json`](schemas/ranking.schema.json). It defines list identity, exact-identifier fields, candidate identity, integer score bounds, and response/error shapes.

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

### Normative fusion policy

The default policy `rrf-v1` uses `k = 60`; for each unique `list_id`, contribution is the integer `floor(10^12 / (60 + rank))`, and candidate score is the sum of contributions. Duplicate candidate occurrences within one list count only at their earliest rank. Exact identifier matches form a primary tier based on the request's `exact_identifiers` and candidate `matched_exact_identifiers`. All remaining ties use the deterministic key in the semantics section. Implementations must use integer arithmetic only for fusion. The response policy identity is `{\"name\":\"rrf-v1\",\"version\":\"1\"}` and includes the integer score, scale `10^12`, score semantics, and `matched_exact_identifiers` unchanged from the input candidate. Exact-match tiering is guaranteed through final Gateway output; Reranking must preserve exact candidates and Gateway restores the exact tier after Reranking. Raw source scores and semantics are retained as evidence, not compared across retrieval sources.

## Approval gate

Review with Lexical Retrieval, Vector Retrieval, Gateway orchestration, Reranking, common candidate identity/provenance, and end-to-end retrieval acceptance tests before implementation.


Candidate identity follows the shared REST rules: `source_id`, `revision_sequence`, `chunk_id`, and `chunker: {profile, version}`. Do not merge evidence from distinct source revisions. Lexical and vector candidate contracts must provide a 1-based `retrieval_rank` so RRF is executable.
