# Gateway Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Provide the client-facing CE REST API and orchestrate bounded workflows across logical services. Own request validation, local deployment restrictions where required, scope propagation, request budgets, query planning, service selection, partial-result policy, prompt-context assembly/compression, and final response composition. Query Planning is a Gateway capability, not a separate initial service.

Gateway does not own Memory/Knowledge/Graph/Thompson/Learning/Index domain state. It calls every logical service through REST, even in the single-process deployment. It must not access another service's storage or invoke its implementation directly.

## Endpoints

- POST /api/v1/requests: process a client request and return a bounded response with provenance.
- GET /api/v1/gateway/health: process liveness.
- GET /api/v1/gateway/ready: readiness to accept client requests under configured dependency policy.

The public request/response schemas below are normative for the initial contract. Generalized authentication is deferred; only local access restrictions required by the single-instance deployment apply.

## Orchestration semantics

- V1 query planning uses the original query only; query expansion is deferred. `variants_used` is always 1. This avoids ambiguous multi-list fusion and keeps the first slice measurable.
- Build a bounded plan using Intent Classification and Entity/Identifier Extraction where useful; choose Memory/Knowledge/Graph and lexical/vector retrieval calls based on intent, scope, and request budget. The intent vocabulary is `memory_recall`, `knowledge_lookup`, `relationship_exploration`, `troubleshooting`, `explanation`, `decision_support`, and `general`; unknown/low-confidence intent uses the bounded `general` plan. Query expansion is capped at 3 total variants including the original query, and 
- Run independent calls concurrently only when the plan, deadline, and failure policy permit. All service calls use REST and propagate correlation, deadline, cancellation, and authorized scope.
- Invoke Ranking to fuse candidate sets; invoke Reranking only for a bounded candidate set when policy and remaining budget permit. Gateway sends `exact_identifiers` (at most 32, preserved byte-for-byte/code-point-for-code-point) to Ranking; candidates carry `matched_exact_identifiers` only when their returned evidence contains an exact case-sensitive match. Ranking gives exact-identifier matches a primary tier before RRF score.
- Assemble prompt context with explicit token budget, relevance, recency/authority policy where applicable, provenance, and compression rules. Compression must preserve facts, decisions, constraints, identifiers, and evidence links; it must not silently change meaning.
- Provider prompt-cache optimization is a separate concern from generic response caching. Stable prefixes may be reused only when provider semantics and privacy scope allow it.
- Automatic prompt-time memory injection must work without a manual memory instruction or special prefix. Hook/adapters call Gateway through the public contract and must not bypass service ownership.
- Partial dependency failure follows this normative v1 matrix: (1) Lexical or Vector fails while the other succeeds: rank the successful path, return `status=partial`, `degraded=true`, and a failure entry. (2) Both Lexical and Vector fail: return `status=failed`, no candidates, and failure entries, never healthy empty success. (3) Graph fails: if another planned retrieval path succeeds, return partial/degraded; if Graph was the only planned source, return failed. (4) Ranking fails: return failed because Gateway will not invent a ranking. (5) Reranking fails: use the already-ranked order, mark partial/degraded, and record the failure; in hook mode Reranking is skipped. (6) One owner verification endpoint fails: fail closed for candidates from that owner while retaining verified candidates from other owners and mark partial/degraded. If no safe candidates remain, return failed, not empty success. (7) Query understanding failure uses the bounded `general` plan only if sufficient budget remains; otherwise fail open in hook mode and fail explicitly for interactive mode. An unavailable retrieval service is not treated as a successful no-match. For every candidate returned to a client or prompt context, Gateway batches source IDs and `revision_sequence` values by owner and calls Memory/Knowledge revision-verification REST endpoints before presenting candidates as current. A missing/tombstoned source or revision mismatch is filtered. If required verification is unavailable, the candidate is not exposed as current and the response marks freshness degradation; if no safe candidates remain, return an explicit degraded/failed outcome rather than claiming a successful empty search.
- The default interactive deadline is 5,000 ms; the prompt-hook deadline is 1,500 ms. These are hard end-to-end deadlines, not promises that every dependency succeeds. Phase budgets are normative:

| Phase | Prompt hook | Interactive |
|---|---:|---:|
| Intent + entity/identifier extraction | 150 ms | 400 ms |
| Concurrent retrieval fan-out | 550 ms | 1,800 ms |
| Canonical freshness verification | 250 ms | 600 ms |
| Ranking | 100 ms | 250 ms |
| Reranking | skipped | 1,000 ms |
| Context assembly/compression | 150 ms | 350 ms |
| Unallocated safety margin | 300 ms | 600 ms |

Each outbound call receives the lesser of its phase cap and remaining end-to-end time. Independent retrieval calls run concurrently, never each with a fresh full deadline. Hook mode skips Reranking. Total candidate budget is 100: retrieve/verify at most 80 initial candidates, then at most one bounded refill of 20 candidates if fewer than the requested final limit survive freshness checks and at least 250 ms remains. Refill excludes previously seen canonical candidate identities. No second refill is allowed. Retries are bounded and respect idempotency and cancellation. Tests assert the phase caps and overall deadline under controlled gates.
- Preserve request ID, selected plan/policy versions, candidate provenance, source revisions, and model/profile versions in safe response metadata. Do not log raw prompts or sensitive source text by default.

### Public request and response schemas

Request `POST /api/v1/requests`:

~~~json
{
  "request_id": "correlation-id",
  "query": "How are source revisions published?",
  "scope": {"type": "project", "id": "project-id", "visibility": "private"},
  "context_budget": {"unit": "provider_tokens", "model": "configured-target-model", "max": 1200},
  "mode": "prompt_recall"
}
~~~

`query` is required and bounded by the configured request limit. `scope` is required unless this endpoint's deployment profile defines one unambiguous default. `context_budget` is bounded; the provider adapter must use the named target model's token counting when available and otherwise report that a conservative estimate was used. `mode` is `prompt_recall`, `interactive`, or `lookup`.

Response:

~~~json
{
  "request_id": "correlation-id",
  "context": "Bounded assembled context",
  "candidates": [],
  "degraded": false,
  "failures": [],
  "plan": {"intent": "general", "variants_used": 1, "policy_version": "0.1"},
  "freshness": "verified",
  "truncated": false
}
~~~

`status` is `complete`, `partial`, or `failed`; `index_freshness` is `current`, `pending_index`, or `unknown`. `degraded` and `failures` distinguish a partial workflow from a successful no-match. On a prompt-hook deadline or total dependency failure, the adapter fails open to the original prompt with no injected context, records a safe diagnostic, and must not claim that no memory exists. Interactive callers receive the documented error envelope when no safe result can be produced.

## Errors and fallback

Use the common REST error envelope. Distinguish invalid request, unauthorized scope, budget/deadline exceeded, dependency unavailable, partial workflow failure, and internal failure. Fallback to pre-reranked candidates or partial results only when explicitly allowed by workflow policy and disclose degraded status in response metadata.

## Acceptance tests

1. Client request traverses service REST contracts only; no direct cross-service calls/storage access.
2. With a fake clock and gated REST dependencies, assert every phase budget, the 1,500 ms hook deadline, the 5,000 ms interactive deadline, the one-refill maximum, and the 100-candidate total cap.
3. Verify each dependency-failure combination in the normative degradation matrix.
2. Scope partition is propagated and required local access restrictions are enforced by the owning service.
3. Deadlines/cancellation propagate; retries and total attempts are bounded.
4. Intent/entity outputs influence planning but never alter scope partition or required local access restrictions.
5. Ranking/Reranking use bounded candidates and explicit failure/fallback behavior.
6. Context assembly respects token budget and preserves required provenance/identifiers/constraints.
7. Automatic prompt-time memory injection works without manual prompt tricks.
8. Provider prompt caching is distinct from response caching and obeys privacy/profile rules.
9. Partial failure differs from valid no-match and is visible to callers.
10. Logs avoid raw prompts/sensitive content by default.
11. Health and readiness semantics are distinct.
12. Tests do not claim federation safety solely from same-process execution.

## Machine-checkable schema and isolated testing

The normative public request/response schema is [`schemas/gateway.schema.json`](schemas/gateway.schema.json). The Gateway unit/contract suite MUST run without any real downstream service: mock each dependency at its REST boundary and verify outbound path, headers, schema, deadline, retry count, idempotency, failure mapping, and cancellation. A separate dispatcher integration suite exercises real REST dispatch.

## Approval gate

Review with every service contract, hook/client adapters, prompt-context requirements, security/scope policy, and end-to-end acceptance workflows before implementation.
