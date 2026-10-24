# Lexical Retrieval Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Retrieve bounded candidates from indexed lexical representations using a named lexical profile, authorized scope, and query terms. Own lexical retrieval behavior, profile compatibility, candidate evidence, and retrieval limits. Call Index through REST for low-level lexical lookup and statistics. Never access Index storage directly.

BM25 and similar scoring methods are strategies behind this service, not separate services by default. This service does not own source records, tokenization, cross-path fusion, final ranking, reranking, or Gateway query planning.

## Endpoints

- POST /api/v1/lexical-retrieval/search
- GET /api/v1/health
- GET /api/v1/ready

## Contract

Requests identify the query, authorized scope, lexical profile and version, tokenized terms, optional narrowing filters, and candidate limit. Terms must come from Tokenization under the named profile. Reject mismatches rather than silently retokenizing. Scope is enforced server-side; caller filters may narrow access but cannot expand it. Initial maximum is 100 candidates.

Responses include chunk/source identity, opaque source revision ID, revision_sequence, bounded evidence text, score and score semantics, matched-term evidence, provenance, and a truncation indicator. Candidate identity follows the common REST tuple: source ID, revision_sequence, chunk ID, and chunker profile/version. Scores are meaningful only within their declared semantics/profile; Gateway and Ranking must not assume lexical and vector scores are directly comparable.

Corpus statistics must be limited to the authorized corpus and compatible profile. Empty terms are invalid unless a profile explicitly defines behavior. Valid no-match returns an empty successful result. Index unavailable, stale/tombstoned evidence, and incompatible profiles are not successful no-matches.

Calls to Index use REST only. Propagate request ID, deadline, cancellation, and scope. Retry transient failures only within remaining budget. Do not log raw queries or candidate text by default.

## Errors

Use the common error envelope. Distinguish invalid query/profile, unauthorized scope, incompatible lexical profile, invalid limit, Index unavailable/not ready, deadline exceeded, and internal failure.

## Acceptance tests

1. Profile/token mismatch is rejected.
2. Scope enforcement prevents unauthorized candidates and corpus-statistics leakage.
3. Results are bounded, deterministic under score ties, and include provenance.
4. No-match differs from Index unavailable/not-ready.
5. Scores declare semantics and are not globally comparable.
6. Index access is REST-only.
7. Deadline, cancellation, and bounded retry behavior are tested.
8. Stale/tombstoned revisions are never returned.
9. Logs omit raw query and candidate text by default.
10. Single-process tests do not claim federation safety.

## Approval gate

Review with Index, Tokenization, Ranking, Vector Retrieval, Gateway orchestration, scope authorization, and end-to-end workflows before implementation.
