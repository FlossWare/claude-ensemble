# Gateway Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Provide the client-facing CE REST API and orchestrate bounded workflows across logical services. Own request validation, authentication/policy integration, scope propagation, request budgets, query planning, service selection, partial-result policy, prompt-context assembly/compression, and final response composition. Query Planning is a Gateway capability, not a separate initial service.

Gateway does not own Memory/Knowledge/Graph/Thompson/Learning/Index domain state. It calls every logical service through REST, even in the single-process deployment. It must not access another service's storage or invoke its implementation directly.

## Endpoints

- POST /api/v1/requests: process a client request and return a bounded response with provenance.
- GET /api/v1/health: process liveness.
- GET /api/v1/ready: readiness to accept client requests under configured dependency policy.

Exact public request/response schema and authentication mechanism must be finalized against the deployment and client adapter requirements before implementation.

## Orchestration semantics

- Build a bounded plan using Intent Classification and Entity/Identifier Extraction where useful; choose Memory/Knowledge/Graph and lexical/vector retrieval calls based on intent, scope, and request budget.
- Run independent calls concurrently only when the plan, deadline, and failure policy permit. All service calls use REST and propagate correlation, deadline, cancellation, and authorized scope.
- Invoke Ranking to fuse candidate sets; invoke Reranking only for a bounded candidate set when policy and remaining budget permit.
- Assemble prompt context with explicit token budget, relevance, recency/authority policy where applicable, provenance, and compression rules. Compression must preserve facts, decisions, constraints, identifiers, and evidence links; it must not silently change meaning.
- Provider prompt-cache optimization is a separate concern from generic response caching. Stable prefixes may be reused only when provider semantics and privacy scope allow it.
- Automatic prompt-time memory injection must work without a manual memory instruction or special prefix. Hook/adapters call Gateway through the public contract and must not bypass service ownership.
- Partial dependency failure is explicit and governed by a documented workflow policy. An unavailable retrieval service is not treated as a successful no-match. For prompt-time memory recall and any request that requires current source truth, Gateway verifies candidate revision_sequence against Memory/Knowledge canonical state before presenting it as current. If verification is required but unavailable, do not present stale candidates as current; report degraded/failed freshness status according to workflow policy.
- Deadlines are end-to-end budgets; each downstream call gets only the remaining time. Retries are bounded and respect idempotency and cancellation.
- Preserve request ID, selected plan/policy versions, candidate provenance, source revisions, and model/profile versions in safe response metadata. Do not log raw prompts or sensitive source text by default.

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
