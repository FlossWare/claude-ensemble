# Gateway Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Provide the client-facing CE REST API and orchestrate bounded workflows across logical services. Own request validation, authentication/policy integration, scope propagation, request budgets, query planning, service selection, partial-result policy, prompt-context assembly/compression, and final response composition. Query Planning is a Gateway capability, not a separate initial service.

Gateway does not own Memory/Knowledge/Graph/Thompson/Learning/Index domain state. It calls every logical service through REST, even in the single-process deployment. It must not access another service's storage or invoke its implementation directly.

## Endpoints

- POST /api/v1/requests: process a client request and return a bounded response with provenance.
- GET /api/v1/gateway/health: process liveness.
- GET /api/v1/gateway/ready: readiness to accept client requests under configured dependency policy.

The public request/response schemas below are normative for the initial contract. Generalized authentication is deferred; only local access restrictions required by the single-instance deployment apply.

## Orchestration semantics

- Build a bounded plan using Intent Classification and Entity/Identifier Extraction where useful; choose Memory/Knowledge/Graph and lexical/vector retrieval calls based on intent, scope, and request budget. The intent vocabulary is `memory_recall`, `knowledge_lookup`, `relationship_exploration`, `troubleshooting`, `explanation`, `decision_support`, and `general`; unknown/low-confidence intent uses the bounded `general` plan. Query expansion is capped at 3 total variants including the original query, and all variants share the same overall deadline and candidate budget.
- Run independent calls concurrently only when the plan, deadline, and failure policy permit. All service calls use REST and propagate correlation, deadline, cancellation, and authorized scope.
- Invoke Ranking to fuse candidate sets; invoke Reranking only for a bounded candidate set when policy and remaining budget permit.
- Assemble prompt context with explicit token budget, relevance, recency/authority policy where applicable, provenance, and compression rules. Compression must preserve facts, decisions, constraints, identifiers, and evidence links; it must not silently change meaning.
- Provider prompt-cache optimization is a separate concern from generic response caching. Stable prefixes may be reused only when provider semantics and privacy scope allow it.
- Automatic prompt-time memory injection must work without a manual memory instruction or special prefix. Hook/adapters call Gateway through the public contract and must not bypass service ownership.
- Partial dependency failure is explicit and governed by a documented workflow policy. An unavailable retrieval service is not treated as a successful no-match. For every candidate returned to a client or prompt context, Gateway batches source IDs and `revision_sequence` values by owner and calls Memory/Knowledge revision-verification REST endpoints before presenting candidates as current. A missing/tombstoned source or revision mismatch is filtered. If required verification is unavailable, the candidate is not exposed as current and the response marks freshness degradation; if no safe candidates remain, return an explicit degraded/failed outcome rather than claiming a successful empty search.
- The caller deadline is an end-to-end budget with a 5-second default from the common REST contract; the prompt-hook adapter may configure a shorter deadline. Each downstream call gets only the remaining time, with a configured bounded per-call cap and explicit time reserved for freshness verification, ranking, and context assembly. Independent retrieval paths run concurrently against the same remaining budget rather than each receiving a fresh full timeout. Retries are bounded and respect idempotency and cancellation. Acceptance tests record total and per-hop latency, including degraded paths.
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

`degraded` and `failures` distinguish a partial workflow from a successful no-match. On a prompt-hook deadline or total dependency failure, the adapter fails open to the original prompt with no injected context, records a safe diagnostic, and must not claim that no memory exists. Interactive callers receive the documented error envelope when no safe result can be produced.

## Errors and fallback

## Errors and fallback

Use the common REST error envelope. Distinguish invalid request, unauthorized scope, budget/deadline exceeded, dependency unavailable, partial workflow failure, and internal failure. Fallback to pre-reranked candidates or partial results only when explicitly allowed by workflow policy and disclose degraded status in response metadata.

## Acceptance tests

1. Client request traverses service REST contracts only; no direct cross-service calls/storage access.
2. Scope and authorization are propagated and enforced by target services.
3. Deadlines/cancellation propagate; retries and total attempts are bounded.
4. Intent/entity outputs influence planning but never grant authorization.
5. Ranking/Reranking use bounded candidates and explicit failure/fallback behavior.
6. Context assembly respects token budget and preserves required provenance/identifiers/constraints.
7. Automatic prompt-time memory injection works without manual prompt tricks.
8. Provider prompt caching is distinct from response caching and obeys privacy/profile rules.
9. Partial failure differs from valid no-match and is visible to callers.
10. Logs avoid raw prompts/sensitive content by default.
11. Health and readiness semantics are distinct.
12. Tests do not claim federation safety solely from same-process execution.

## Approval gate

Review with every service contract, hook/client adapters, prompt-context requirements, security/scope policy, and end-to-end acceptance workflows before implementation.
