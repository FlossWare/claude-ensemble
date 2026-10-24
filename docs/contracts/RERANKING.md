# Reranking Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Perform a second-stage assessment of a small, bounded candidate set after retrieval and initial Ranking. Own reranking policy/model selection, pairwise or listwise assessment, bounded evidence, and policy/model provenance. It does not retrieve candidates, access Index, own source records, or replace initial candidate fusion.

Gateway decides whether reranking is needed, selects the candidate set, enforces authorization and budgets, and orchestrates the call. Reranking must not call other CE services directly.

## Endpoints

- POST /api/v1/reranking/rerank
- GET /api/v1/health
- GET /api/v1/ready

## Request

~~~json
{
  "request_id": "correlation-id",
  "profile": {"name": "default-reranker", "version": "0.1"},
  "query": "How are source revisions published?",
  "candidates": [{
    "chunk_id": "stable-chunk-id",
    "source_id": "knowledge:project:docs/design.md",
    "source_revision": "rev-17",
    "revision_sequence": 17,
    "text": "Bounded candidate evidence",
    "prior_rank": 1,
    "prior_score": 0.82,
    "provenance": {"ranking_policy_version": "0.1", "chunker_profile": "markdown-default", "chunker_version": "0.1"}
  }],
  "limit": 10
}
~~~

## Response

~~~json
{
  "profile": {"name": "default-reranker", "version": "0.1"},
  "candidates": [{
    "chunk_id": "stable-chunk-id",
    "source_id": "knowledge:project:docs/design.md",
    "source_revision": "rev-17",
    "rerank": 1,
    "score": 0.91,
    "score_semantics": "reranker-profile-score",
    "evidence": {"kind": "model-assessment", "version": "model-revision"},
    "provenance": {"ranking_policy_version": "0.1"}
  }],
  "request_id": "correlation-id"
}
~~~

## Semantics

- Candidate count, query length, per-candidate text, total input tokens, output count, and wall-clock time are bounded by the configured profile.
- Preserve candidate identity and provenance. The reranker may reorder but must not invent, mutate, or merge source identities. If candidates are filtered, report bounded reasons/statuses.
- Output scores are specific to the reranker profile and are not assumed comparable to lexical, vector, or initial ranking scores.
- Model/provider identity, version, prompt/template version where relevant, and scoring policy are recorded in the response provenance. Any provider routing must follow approved data-handling policy.
- Deterministic behavior is required when using deterministic strategies. If a model is nondeterministic, the contract records that limitation and tests bounds, identity preservation, and stable error semantics rather than claiming exact repeatability.
- Gateway owns timeout/fallback policy. A reranking failure must be explicit so Gateway may use the already-ranked candidates under its policy; the reranker must not silently claim success with unmodified results.
- Do not log raw query/candidate text by default.

## Errors

Use the common error envelope. Distinguish invalid candidate set, unknown profile, size/token budget exceeded, provider unavailable/rate-limited, deadline exceeded, unauthorized processing policy, and internal failure.

## Acceptance tests

1. Candidate identity and provenance are preserved exactly.
2. Output is bounded and never adds candidates not supplied in the request.
3. Score semantics and profile/model/template versions are explicit.
4. Timeout/provider failure is distinct from a valid reranking result.
5. Gateway fallback can use prior Ranking results without reranker-side hidden behavior.
6. Input/output bounds and privacy-safe logging are enforced.
7. Service makes no direct CE service/storage calls.
8. Provider policy is enforced and test doubles are separated from integration tests.

## Approval gate

Review with Ranking, Gateway budgets/fallback, candidate provenance, provider policy, and end-to-end retrieval workflows before implementation.


Candidate identity follows the shared REST rules: source ID, revision sequence, chunk ID, and chunker profile/version. Do not add, merge, or silently substitute candidates from distinct source revisions.
