# Lexical Retrieval Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Retrieve bounded candidates from indexed lexical representations using a named lexical profile, canonical scope partition, and query terms. Own lexical retrieval behavior, profile compatibility, candidate evidence, and retrieval limits. Call Index through REST for low-level lexical lookup and statistics. Never access Index storage directly.

Index returns term-frequency evidence and scope/profile-specific corpus statistics only. Lexical Retrieval owns BM25 and other lexical scoring algorithms and produces its own rank order; Index does not calculate or return a final BM25 score. BM25 and similar scoring methods are strategies behind this service, not separate services by default. This service does not own source records, tokenization, cross-path fusion, final ranking, reranking, or Gateway query planning.

## Endpoints

- POST /api/v1/lexical-retrieval/search (internal-only in v1; reachable only through the local REST dispatcher)
- GET /api/v1/lexical-retrieval/health
- GET /api/v1/lexical-retrieval/ready

## Contract

Requests identify the query using bounded original `query_text`, canonical scope partition, lexical profile and version, optional narrowing filters, and candidate limit. The request does not accept derived `terms`. Before scoring, Lexical Retrieval resolves the exact `{name,version}` bundle through Index's versioned profile REST endpoint, verifies the digest against `index_profile.digest`, and requires the request's lexical/tokenization component identities to match that bundle. No local or current-profile fallback is allowed for a pinned query. V1 does not expose `page_token`, `next_page_token`, or refill. Index returns a deterministic bounded candidate pool; Lexical Retrieval computes `bm25-v1` over that pool, assigns 1-based ranks, and sets `truncated=true` when Index reports omitted eligible candidates. The caller-supplied `index_generation` and `index_profile.digest` must match the selected generation; otherwise return `409 profile_mismatch` or `409 generation_not_found`. Lexical Retrieval MUST call Tokenization over REST with the original `query_text` and the exact tokenization profile in the pinned Index bundle. It validates that the returned terms identify that profile and retains their provenance. Gateway does not tokenize locally; callers cannot submit pre-tokenized terms, and Lexical Retrieval must not silently substitute a local tokenizer or current profile. Scope partition filters are enforced server-side; caller filters may narrow the selected partition but cannot broaden it. The endpoint is internal to the local REST dispatcher and is not part of the externally exposed Gateway API. Initial maximum is 100 candidates. If the bounded pool is truncated, return the available ranked candidates with `truncated=true`; Gateway decides partial/degraded status after freshness verification and does not request another page in v1.

Index returns candidate text, term-frequency/document-length evidence, and scope/profile-specific corpus statistics. Lexical Retrieval owns lexical scoring and rank assignment. The v1 default is `bm25-v1` with `k1=1.2` and `b=0.75`. Each indexed chunk is a document: `N` is the count of eligible chunks in the requested scope/profile, `df(q)` is the number of those chunks containing term `q`, `dl` is the chunk's indexed term count, and `avgdl` is the mean `dl` across that corpus. For each unique query term, compute `idf(q)=ln(1+(N-df(q)+0.5)/(df(q)+0.5))` and `score += idf(q) * tf(q,D)*(k1+1)/(tf(q,D)+k1*(1-b+b*dl/avgdl))`; terms repeated in the query count once. If `N=0` or `avgdl=0`, return an empty result. Round each final `bm25-v1` score to 9 decimal places using round-half-to-even after IEEE-754 binary64 calculation. Sort by rounded score descending, then `source_id` ascending, `revision_sequence` descending, `chunk_id` ascending, and chunker profile/version ascending by Unicode code-point order. Document frequency and average length are computed only within the requested scope partition and pinned lexical profile. Lexical Retrieval returns 1-based `retrieval_rank`, `score`, and `score_semantics=bm25-v1`. Candidate identity follows the common REST tuple: source ID, revision_sequence, chunk ID, and chunker profile/version. Gateway and Ranking treat BM25 values as evidence and never compare them numerically with vector distances/similarities.

Corpus statistics must be limited to the selected scope partition and compatible profile. Empty terms are invalid unless a profile explicitly defines behavior. Valid no-match returns an empty successful result. Index unavailable, stale/tombstoned evidence, and incompatible profiles are not successful no-matches.

Calls to Index use REST only. Propagate request ID, deadline, cancellation, and scope. Retry transient failures only within remaining budget. Do not log raw queries or candidate text by default.

## Normative request/response schema

Request fields: `request_id`, `query_id`, bounded non-empty original `query_text`, canonical `scope`, `index_generation`, `index_profile` (`name`, `version`, `digest`), `lexical_profile` (`name`, `version`), optional `source_ids`/exact `source_revisions`, and `limit` (1–100). Lexical Retrieval obtains terms from Tokenization over REST under the pinned bundle. Response fields: `query_id`, the same pinned `index_generation`, effective profiles, `candidates`, `truncated`, and `request_id`. Each candidate contains `source_id`, opaque `source_revision`, `revision_sequence`, `chunk_id`, `chunker` profile/version, bounded `text`, 1-based `retrieval_rank`, `score`, `score_semantics=bm25-v1`, matched-term evidence, and provenance. Ranks are assigned by Lexical Retrieval after applying `bm25-v1` to Index's term-frequency evidence and corpus statistics. Calculate with IEEE-754 binary64, round final scores to 9 decimal places using round-half-to-even, sort by rounded score descending then canonical candidate identity ascending, and assign 1-based ranks; Ranking's RRF consumes ranks, never floating-point scores. Index does not calculate BM25 or assign lexical ranks.

## Endpoint status codes

- `POST /api/v1/lexical-retrieval/search`: `200` with a bounded candidate list, including an empty list for a successful no-match.
- Invalid request/empty terms/invalid limit: `400 invalid_request`.
- Unknown or retired profile / incompatible tokenization profile: `422 unsupported_profile` or `422 incompatible_representation`.
- Index unavailable/not ready: `503 dependency_unavailable` or `503 not_ready`; deadline: `504 deadline_exceeded`.
- Search and Index lookup are internal logical-service endpoints through the local REST dispatcher, not external Gateway APIs.

## Machine-checkable schemas

The normative Lexical Retrieval request/response JSON Schema is in [`schemas/lexical-retrieval.schema.json`](schemas/lexical-retrieval.schema.json). It defines query/profile fields, candidate identity, score semantics, bounds, and errors.

## Errors

Use the common error envelope. Distinguish invalid query/profile, uncanonical scope partition, incompatible lexical profile, invalid limit, Index unavailable/not ready, deadline exceeded, and internal failure.

## Acceptance tests

1. Profile/token mismatch is rejected, including Tokenization returning a different profile identity than the pinned bundle.
2. A public-query fixture traces Gateway → Lexical Retrieval → Tokenization → Index; each intermediate payload is validated, and no component invents terms locally.
2. Scope partition filters prevent cross-partition candidates and corpus-statistics leakage.
3. Results are bounded, deterministic under score ties, and include provenance.
4. No-match differs from Index unavailable/not-ready.
5. Scores declare semantics and are not globally comparable.
6. Index access is REST-only.
7. Deadline, cancellation, and bounded retry behavior are tested.
8. Stale/tombstoned revisions are never returned.
9. Logs omit raw query and candidate text by default.

## Approval gate

Review with Index, Tokenization, Ranking, Vector Retrieval, Gateway orchestration, scope partition filtering, and end-to-end workflows before implementation.
